import discord
from discord.ext import tasks, commands
from discord.app_commands import check, AppCommandError

import asyncio
import time
import json
import re

from mcbot import minecraft, advancements, playtime
from mcbot.constants import *
from mcbot.misc import (
    TOKEN, CHANNEL_ID, CHAT_CHANNEL_ID, RULES_PATH, INFO_PATH, MAP_URL,
    send_message, follow_up, LOG_FILE, SERVER_DIR,
    server_is_running, has_permission, has_dev_permission,
    DevGroup, PlayerGroup, ServerOffline, is_dev_only,
    ShutdownConfirmView, wait_for_server_ready,
    get_log_size, get_spark_health_url, get_tellraw_message,
    send_relay, head_url, get_head_emoji, get_installed_plugins
)

from mcbot.chat import LogTailer, parse_log_line

tailer = LogTailer(LOG_FILE)
no_pings = discord.AllowedMentions.none()

import logging
log = logging.getLogger("mcbot")


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

INACTIVITY_LIMIT = 900  # seconds with an empty server before auto-shutdown
PLAYER_NAME = re.compile(r"^[\w.\-]{1,32}$")

empty_since = None
start_lock = asyncio.Lock()


##################
### BOT THINGS ###
##################


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: AppCommandError):
    if isinstance(error, ServerOffline):
        message = MSG_OFFLINE
    elif isinstance(error, discord.app_commands.CheckFailure):
        message = MSG_NO_PERMISSION
    else:
        log.error("Unhandled command error", exc_info=error)
        message = MSG_FAIL(error)

    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await send_message(interaction, message, ephemeral=True)


@tasks.loop(seconds=1)
async def chat_relay():
    channel = bot.get_channel(CHAT_CHANNEL_ID)
    if channel is None:
        return

    for line in tailer.read_new_lines():
        event = parse_log_line(line)
        if event is None:
            continue

        kind = event[0]
        esc = discord.utils.escape_markdown

        if kind == "chat":
            _, name, msg = event
            await send_relay(channel, f"**{esc(name)}**: {esc(msg)}",
                             content=esc(msg), username=name, avatar=head_url(name))
            continue

        if kind == "join":
            text = f"➡️ **{esc(event[1])}** joined the game"
        elif kind == "leave":
            text = f"⬅️ **{esc(event[1])}** left the game"
        elif kind == "advancement":
            _, name, verb, title = event
            icon = {"made the advancement": "🏆", "completed the challenge": "🌟", "reached the goal": "🎯"}[verb]
            text = f"{icon} **{esc(name)}** has {verb} **{esc(title)}**"
        elif kind == "death":
            text = f"💀 **{esc(event[1])}** {esc(event[2])}"
        else:
            text = f"ℹ️ {esc(event[1])}"

        await send_relay(channel, text)


@chat_relay.before_loop
async def before_chat_relay():
    await bot.wait_until_ready()


@tasks.loop(seconds=30)
async def inactivity_monitor():
    global empty_since

    if not await asyncio.to_thread(minecraft.is_server_running):
        empty_since = None
        return

    try:
        player_count, _ = minecraft.get_online_players()

        if player_count > 0:
            empty_since = None
            return

        if empty_since is None:
            empty_since = time.monotonic()
            log.info("Server empty. Starting inactivity timer.")
            return

        if time.monotonic() - empty_since >= INACTIVITY_LIMIT:
            log.info("Inactivity limit reached. Stopping server.")
            minecraft.stop_server()

            # Wait for systemd to confirm the server has stopped
            for _ in range(30):
                if not await asyncio.to_thread(minecraft.is_server_running):
                    await notify_channel(MSG_SHUTDOWN)
                    break

                await asyncio.sleep(2)
            empty_since = None

    except (ConnectionRefusedError, TimeoutError):
        # server is still booting, RCON isn't open yet 
        empty_since = None
    except Exception:
        log.exception("Inactivity monitor error")
        empty_since = None


@inactivity_monitor.before_loop
async def before_monitor():
    await bot.wait_until_ready()


async def setup_hook():
    await bot.tree.sync()
    inactivity_monitor.start()
    if CHAT_CHANNEL_ID and not chat_relay.is_running():
        chat_relay.start()

bot.setup_hook = setup_hook


@bot.event
async def on_ready():
    log.info(f"Logged in as {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not CHAT_CHANNEL_ID or message.channel.id != CHAT_CHANNEL_ID:
        return
    if not await asyncio.to_thread(minecraft.is_server_running):
        return

    text = " ".join(message.clean_content.split())[:256] or "[attachment]"
    payload = {"text": "", "extra": [
        {"text": "[Discord] ", "color": "blue", "bold": True},
        {"text": f"{message.author.display_name}: ", "color": "aqua"},
        {"text": text, "color": "white"},
    ]}
    try:
        minecraft.send_command(f"tellraw @a {json.dumps(payload, ensure_ascii=False)}")
    except Exception as e:
        log.exception(f"Failed to relay Discord message to Minecraft: {e}")


async def notify_channel(message):
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        channel = await bot.fetch_channel(CHANNEL_ID)
    await channel.send(message)


#############################
### SERVER SLASH COMMANDS ###
#############################


@bot.tree.command(name="map", description="Get the link to the live map")
@discord.app_commands.guild_only()
@check(has_permission)
async def map_command(interaction: discord.Interaction):
    if not await asyncio.to_thread(minecraft.is_server_running):
        await send_message(interaction, MSG_OFFLINE, ephemeral=True)
        return

    await send_message(interaction, f"{MSG_MAP}{MAP_URL}")


@bot.tree.command(name="serverstatus", description="Check Minecraft server status")
@discord.app_commands.guild_only()
@check(has_permission)
async def serverstatus(interaction: discord.Interaction):
    await interaction.response.defer()

    if not await asyncio.to_thread(minecraft.is_server_running):
        await interaction.followup.send(MSG_OFFLINE)
        return

    try:
        player_count, player_names = minecraft.get_online_players()

        lines = []
        for name in player_names:
            icon = await get_head_emoji(bot, name) or "•"
            lines.append(f"{icon} {name}")
        player_list = "\n".join(lines) if lines else "Nobody is online."

        await interaction.followup.send(
            f"{MSG_ONLINE}\nPlayers: {player_count}\n\n**Online players:**\n{player_list}"
        )

    except (ConnectionRefusedError, TimeoutError):
        await interaction.followup.send(MSG_STARTING)
    except Exception as e:
        log.exception(f"Exception: `{e}`")
        await interaction.followup.send(MSG_STARTING)


@bot.tree.command(name="startserver", description="Start the Minecraft server")
@discord.app_commands.guild_only()
@check(has_permission)
async def startserver(interaction: discord.Interaction):
    if start_lock.locked():
        await send_message(interaction, MSG_STARTING)
        return

    async with start_lock:
        if await asyncio.to_thread(minecraft.is_server_running):
            await send_message(interaction, MSG_ONLINE)
            return

        await interaction.response.defer()

        try:
            await asyncio.to_thread(minecraft.start_server)
            ready = await wait_for_server_ready()

            if ready:
                await notify_channel(MSG_ONLINE)
                await follow_up(interaction, "Minecraft started successfully!")
            else:
                await follow_up(interaction, "Minecraft did not become ready within 3 minutes.")

        except Exception as e:
            await follow_up(interaction, f"Failed to start Minecraft: {e}")


@bot.tree.command(name="serverrules", description="Display the Minecraft server rules")
async def serverrules(interaction: discord.Interaction):
    try:
        with open(RULES_PATH, "r", encoding="utf-8") as file:
            rules = file.read().strip()
    except FileNotFoundError:
        rules = ""

    plugins = await asyncio.to_thread(get_installed_plugins)
    plugin_list = "\n".join(f"• {name}" for name in plugins) if plugins else "None installed."

    await send_message(interaction, f"{MSG_RULES}{rules}\n\n{MSG_PLUGINS}{plugin_list}"[:1990])


@bot.tree.command(name="help", description="Show bot commands")
async def help_command(interaction: discord.Interaction):
    user_commands, dev_commands = [], []
    for command in bot.tree.walk_commands():
        if isinstance(command, discord.app_commands.Group):
            continue
        entry = f"**/{command.qualified_name}**\n{command.description}"
        (dev_commands if is_dev_only(command) else user_commands).append(entry)

    embed = discord.Embed(title=MSG_HELP, color=discord.Color.green())
    embed.add_field(name=MSG_COMMANDS, value="\n\n".join(user_commands)[:1024], inline=False)
    await interaction.response.send_message(embed=embed)

    # Devs also get a private list of the dev-only commands
    if dev_commands and has_dev_permission(interaction):
        dev_embed = discord.Embed(
            title=MSG_DEV_COMMANDS,
            description="\n\n".join(dev_commands)[:4096],
            color=discord.Color.orange(),
        )
        await interaction.followup.send(embed=dev_embed, ephemeral=True)


@bot.tree.command(name="howto", description="Show server joining instructions")
async def howto_command(interaction: discord.Interaction):
    try:
        with open(INFO_PATH, "r", encoding="utf-8") as file:
            server_info = file.read().strip()
    except FileNotFoundError:
        server_info = ""

    embed = discord.Embed(title=MSG_HOWTO, color=discord.Color.green())
    embed.description = server_info[:4096]
    await interaction.response.send_message(embed=embed)


######################
#### DEV COMMANDS ####
######################


@bot.tree.command(name="shutdown", description="Shut down the Minecraft server")
@discord.app_commands.guild_only()
@check(server_is_running)
@check(has_dev_permission)
async def shutdown(interaction: discord.Interaction):
    await send_message(interaction, MSG_CONFIRM_SHUTDOWN, view=ShutdownConfirmView(interaction), ephemeral=True)


@bot.tree.command(name="sparkhealth", description="Show Minecraft server health (dev only)")
@discord.app_commands.guild_only()
@check(server_is_running)
@check(has_dev_permission)
async def sparkhealth(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        offset = get_log_size()
        minecraft.send_command("spark health")
        url = await asyncio.to_thread(get_spark_health_url, offset)
        if url:
            await follow_up(interaction, f"{MSG_SPARK}{url}")
        else:
            await follow_up(interaction, MSG_FAIL("Couldn't find the Spark health URL in the server log."))
    except Exception as e:
        await follow_up(interaction, MSG_FAIL(e))


@bot.tree.command(name="godtext", description="Send a divine announcement to all Minecraft players")
@discord.app_commands.guild_only()
@check(server_is_running)
@check(has_dev_permission)
async def godtext(interaction: discord.Interaction, message: str):
    if len(message) > 500:
        await send_message(interaction, MSG_TOO_LONG, ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        command = f"tellraw @a {json.dumps(get_tellraw_message(message), ensure_ascii=False)}"
        minecraft.send_command(command)
        await follow_up(interaction, f"Message sent!\n> {message}")

    except Exception as e:
        await follow_up(interaction, MSG_FAIL(e))


#################
### WHITELIST ###
#################


whitelist_group = DevGroup(name="whitelist", description="Manage the Minecraft whitelist", guild_only=True)


@whitelist_group.command(name="add", description="Add a player to the whitelist")
@check(server_is_running)
async def whitelist_add(interaction: discord.Interaction, playername: str):
    if not PLAYER_NAME.match(playername):
        await send_message(interaction, MSG_FAIL(MSG_INVALID), ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        result = minecraft.send_command(f"whitelist add {playername}")
        await follow_up(interaction, MSG_SUCCEED(result))
    except Exception as e:
        await follow_up(interaction, MSG_FAIL(e))


@whitelist_group.command(name="remove", description="Remove a player from the whitelist")
@check(server_is_running)
async def whitelist_remove(interaction: discord.Interaction, playername: str):
    if not PLAYER_NAME.match(playername):
        await send_message(interaction, MSG_FAIL(MSG_INVALID), ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        result = minecraft.send_command(f"whitelist remove {playername}")
        await follow_up(interaction, MSG_SUCCEED(result))
    except Exception as e:
        await follow_up(interaction, MSG_FAIL(e))


@whitelist_group.command(name="list", description="List all whitelisted players")
@check(server_is_running)
async def whitelist_list(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        result = minecraft.send_command("whitelist list")

        names = result.split(": ", 1)[1].split(", ") if ": " in result else []
        listing = "".join(f"{i}. {name}\n" for i, name in enumerate(names, 1))

        await follow_up(interaction, MSG_WHITELIST+listing)

    except Exception as e:
        await follow_up(interaction, MSG_FAIL(e))


advanced_group = PlayerGroup(name="advanced", description="Advancement statistics", guild_only=True)


async def player_autocomplete(interaction: discord.Interaction, current: str):
    if not has_permission(interaction):
        return []
    try:
        names = await asyncio.to_thread(advancements.known_players, SERVER_DIR)
    except Exception:
        return []
    matches = sorted((n for n in names if current.lower() in n.lower()), key=str.lower)
    return [discord.app_commands.Choice(name=n, value=n) for n in matches[:25]]


@advanced_group.command(name="show", description="Show a player's advancement progress")
@discord.app_commands.describe(playername="Minecraft username")
@discord.app_commands.autocomplete(playername=player_autocomplete)
async def advanced_show(interaction: discord.Interaction, playername: str):
    await interaction.response.defer()
    try:
        data = await asyncio.to_thread(advancements.load_all, SERVER_DIR)
    except Exception:
        log.exception("Couldn't read advancement data")
        await interaction.followup.send(MSG_FAIL("Couldn't read advancement data."), ephemeral=True)
        return

    name = next((n for n in data if n.lower() == playername.lower()), None)
    if name is None:
        await interaction.followup.send(
            f"No advancement data found for **{discord.utils.escape_markdown(playername)}**.", ephemeral=True)
        return

    done = data[name]
    total = advancements.total_count(SERVER_DIR)
    if total:
        filled = round(10 * len(done) / total)
        progress = f"**{len(done)}** / {total} ({len(done) * 100 // total}%)\n{'█' * filled}{'░' * (10 - filled)}"
    else:
        progress = f"**{len(done)}** completed"

    recent = sorted(done.items(), key=lambda kv: kv[1], reverse=True)[:5]
    lines = []
    for adv_id, when in recent:
        suffix = f" — {discord.utils.format_dt(when, 'R')}" if when.timestamp() > 0 else ""
        lines.append(f"🏆 **{advancements.get_title(SERVER_DIR, adv_id)}**{suffix}")

    embed = discord.Embed(title=name, color=discord.Color.green())
    embed.set_thumbnail(url=head_url(name))
    embed.add_field(name="Progress", value=progress, inline=False)
    embed.add_field(name="Recent advancements", value="\n".join(lines) or "None yet.", inline=False)
    await interaction.followup.send(embed=embed)


@advanced_group.command(name="top", description="Show the players with the most advancements")
async def advanced_top(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        data = await asyncio.to_thread(advancements.load_all, SERVER_DIR)
    except Exception:
        log.exception("Couldn't read advancement data")
        await interaction.followup.send(MSG_FAIL("Couldn't read advancement data."), ephemeral=True)
        return

    ranking = sorted(data.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))[:10]
    if not ranking:
        await interaction.followup.send("No advancement data yet.")
        return

    total = advancements.total_count(SERVER_DIR)
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (name, done) in enumerate(ranking):
        place = medals[i] if i < 3 else f"`{i + 1}.`"
        icon = await get_head_emoji(bot, name)
        count = f"{len(done)} / {total}" if total else str(len(done))
        lines.append(f"{place} {icon} **{discord.utils.escape_markdown(name)}** — {count}")

    embed = discord.Embed(title="🏆 Advancement leaderboard", description="\n".join(lines),
                          color=discord.Color.gold())
    await interaction.followup.send(embed=embed)


time_group = DevGroup(name="time", description="Player playtime", guild_only=True)


async def dev_player_autocomplete(interaction: discord.Interaction, current: str):
    if not has_dev_permission(interaction):  # Discord skips command checks for autocomplete
        return []
    try:
        names = await asyncio.to_thread(advancements.known_players, SERVER_DIR)
    except Exception:
        return []
    matches = sorted((n for n in names if current.lower() in n.lower()), key=str.lower)
    return [discord.app_commands.Choice(name=n, value=n) for n in matches[:25]]


@time_group.command(name="show", description="Show how long a player has played on the server")
@discord.app_commands.describe(playername="Minecraft username")
@discord.app_commands.autocomplete(playername=dev_player_autocomplete)
async def time_show(interaction: discord.Interaction, playername: str):
    await interaction.response.defer(ephemeral=True)
    try:
        data = await asyncio.to_thread(playtime.load_playtimes, SERVER_DIR)
    except Exception:
        log.exception("Couldn't read playtime data")
        await interaction.followup.send(MSG_FAIL("Couldn't read playtime data."), ephemeral=True)
        return

    name = next((n for n in data if n.lower() == playername.lower()), None)
    if name is None:
        await interaction.followup.send(
            f"No playtime data found for **{discord.utils.escape_markdown(playername)}**.", ephemeral=True)
        return

    embed = discord.Embed(title=name, color=discord.Color.blue())
    embed.set_thumbnail(url=head_url(name))
    embed.add_field(name="Time played", value=playtime.format_duration(data[name]), inline=False)
    await interaction.followup.send(embed=embed, ephemeral=True)


@time_group.command(name="top", description="Show the players with the most playtime")
async def time_top(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        data = await asyncio.to_thread(playtime.load_playtimes, SERVER_DIR)
    except Exception:
        log.exception("Couldn't read playtime data")
        await interaction.followup.send(MSG_FAIL("Couldn't read playtime data."), ephemeral=True)
        return

    ranking = sorted(data.items(), key=lambda kv: (-kv[1], kv[0].lower()))[:10]
    if not ranking:
        await interaction.followup.send("No playtime data yet.", ephemeral=True)
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (name, seconds) in enumerate(ranking):
        place = medals[i] if i < 3 else f"`{i + 1}.`"
        icon = await get_head_emoji(bot, name)
        lines.append(f"{place} {icon} **{discord.utils.escape_markdown(name)}** — {playtime.format_duration(seconds)}")

    embed = discord.Embed(title="⏱️ Playtime leaderboard", description="\n".join(lines),
                          color=discord.Color.blue())
    embed.set_footer(text=f"Total across all players: {playtime.format_duration(sum(data.values()))}")
    await interaction.followup.send(embed=embed, ephemeral=True)


bot.tree.add_command(whitelist_group)
bot.tree.add_command(advanced_group)
bot.tree.add_command(time_group)

if __name__ == "__main__":
    bot.run(TOKEN, root_logger=True)
