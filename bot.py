import discord
from discord.ext import tasks, commands
from discord.app_commands import check, AppCommandError

import asyncio
import time
import json

import minecraft
from constants import *
from misc import *


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

empty_since = None


##################
### BOT THINGS ###
##################


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        send_message(interaction, MSG_FAIL(error), ephemeral=True)


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
            print("Server empty. Starting inactivity timer.")
            return

        elapsed = time.monotonic() - empty_since

        if elapsed >= 900:
            print("15 minutes of inactivity. Stopping server.")
            minecraft.stop_server()

            # Wait for systemd to confirm the server has stopped
            for _ in range(30):
                if not await asyncio.to_thread(minecraft.is_server_running):
                    await notify_channel(MSG_SHUTDOWN)
                    break

                await asyncio.sleep(2)
            empty_since = None

    except Exception as e:
        print(f"Inactivity monitor error: {e}")
        empty_since = None


@inactivity_monitor.before_loop
async def before_monitor():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    await bot.tree.sync()
    if not inactivity_monitor.is_running():
        inactivity_monitor.start()
    print(f"Logged in as {bot.user}")


async def notify_channel(message):
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        channel = await bot.fetch_channel(CHANNEL_ID)
    await channel.send(message)


#############################
### SERVER SLASH COMMANDS ###
#############################

@bot.tree.command(name="serverstatus", description="Check Minecraft server status")
@check(has_permission)
async def serverstatus(interaction: discord.Interaction):
    if not await asyncio.to_thread(minecraft.is_server_running):
        send_message(interaction, MSG_OFFLINE)
        return

    try:
        player_count, player_names = minecraft.get_online_players()

        player_list = "\n".join(
            f"• {name}" for name in player_names
        ) if player_names else "Nobody is online."

        message = f"{MSG_ONLINE}\nPlayers: {player_count}\n\n**Online players:**\n{player_list}"
        send_message(interaction, message)

    except Exception as e:
        send_message(interaction, MSG_STARTING)


@check(has_permission)
@bot.tree.command(name="startserver", description="Start the Minecraft server")
async def startserver(interaction: discord.Interaction):
    if await asyncio.to_thread(minecraft.is_server_running):
        send_message(interaction, MSG_ONLINE)
        return

    await interaction.response.defer()

    try:
        await asyncio.to_thread(minecraft.start_server)
        ready = await wait_for_server_ready()

        if ready:
            notify_channel(MSG_ONLINE)
            follow_up(interaction, "Minecraft started successfully!")
        else:
            follow_up(interaction, "Minecraft did not become ready within 3 minutes.")

    except Exception as e:
        follow_up(interaction, f"Failed to start Minecraft: {e}")


@bot.tree.command(name="serverrules", description="Display the Minecraft server rules")
async def serverrules(interaction: discord.Interaction):
    try:
        with open(rules_path, "r", encoding="utf-8") as file:
            rules = file.read().strip()
    except FileNotFoundError:
        rules = ""
    send_message(interaction, f"{MSG_RULES}{rules}")


@bot.tree.command(name="help", description="Show bot commands and server joining instructions")
async def help_command(interaction: discord.Interaction):
    command_list = []
    for command in bot.tree.get_commands():
        if getattr(command, "dev_only", False):
            continue
        command_list.append(f"**/{command.name}**\n{command.description}")

    try:
        with open(info_path, "r", encoding="utf-8") as file:
            server_info = file.read().strip()
    except FileNotFoundError:
        server_info = ""

    embed = discord.Embed(title=MSG_HELP, color=discord.Color.green())
    embed.add_field(name=MSG_COMMANDS, value="\n\n".join(command_list)[:1024], inline=False)
    embed.add_field(name=MSG_HOWTO, value=server_info[:1024], inline=False)
    await interaction.response.send_message(embed=embed)


######################
#### DEV COMMANDS ####
######################


@bot.tree.command(name="shutdown", description="Shut down the Minecraft server")
@check(has_dev_permission)
@check(server_is_running)
@dev_only
async def shutdown(interaction: discord.Interaction):
    send_message(interaction, MSG_CONFIRM_SHUTDOWN, view=ShutdownConfirmView(), ephemeral=True)


@bot.tree.command(name="sparkhealth", description="Show Minecraft server health (dev only)")
@check(has_dev_permission)
@check(server_is_running)
@dev_only
async def sparkhealth(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        minecraft.send_command("spark health")
        url = get_spark_health_url()
        if url:
            follow_up(interaction, f"{MSG_SPARK}{url}")
        else:
            follow_up(interaction, MSG_FAIL(e))
    except Exception as e:
        follow_up(interaction, MSG_FAIL(e))


@bot.tree.command(name="godtext", description="Send a divine announcement to all Minecraft players")
@check(has_dev_permission)
@check(server_is_running)
@dev_only
async def godtext(interaction: discord.Interaction, message: str):
    if len(message) > 500:
        send_message(interaction, MSG_TOO_LONG, ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        command = f"tellraw @a {json.dumps(get_tellraw_message(message), ensure_ascii=False)}"
        minecraft.send_command(command)
        follow_up(interaction, f"Message sent!\n> {message}")

    except Exception as e:
        follow_up(interaction, MSG_FAIL(e))


#################
### WHITELIST ###
#################


whitelist_group = discord.app_commands.Group(name="whitelist", description="Manage the Minecraft whitelist")


@whitelist_group.command(name="add", description="Add a player to the whitelist")
@check(has_dev_permission)
@check(server_is_running)
@dev_only
async def whitelist_add(interaction: discord.Interaction, playername: str):
    await interaction.response.defer(ephemeral=True)

    try:
        result = minecraft.send_command(f"whitelist add {playername}")
        await interaction.followup.send(
            f"✅ Whitelist add result:\n```{result or 'Command executed.'}```",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to add player: `{e}`",
            ephemeral=True
        )


@whitelist_group.command(name="remove", description="Remove a player from the whitelist")
@check(has_dev_permission)
@check(server_is_running)
@dev_only
async def whitelist_remove(interaction: discord.Interaction, playername: str):
    await interaction.response.defer(ephemeral=True)

    try:
        result = minecraft.send_command(f"whitelist remove {playername}")
        await interaction.followup.send(
            f"✅ Whitelist remove result:\n```{result or 'Command executed.'}```",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to remove player: `{e}`",
            ephemeral=True
        )


@whitelist_group.command(name="list", description="List all whitelisted players")
@check(has_dev_permission)
@check(server_is_running)
@dev_only
async def whitelist_list(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        result = minecraft.send_command("whitelist list")
        if result:
            result = "".join([f"{i+1}. {name}\n" for i, name in enumerate(result.split(": ")[1].split(", "))])

        await interaction.followup.send(
            f"📋 **Minecraft Whitelist:**\n```{result or 'The whitelist is empty.'}```",
            ephemeral=True
        )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to retrieve whitelist: `{e}`",
            ephemeral=True
        )


bot.tree.add_command(whitelist_group)
bot.run(TOKEN)
