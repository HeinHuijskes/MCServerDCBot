import discord
from discord.ext import tasks
from discord.ext import commands
from dotenv import load_dotenv

import asyncio
import time

import os
import re
import json
from pathlib import Path

import minecraft

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("DISCORD_USER_ID", "0"))
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
ROLE_ID = int(os.getenv("DISCORD_ROLE_ID"))
DEV_ROLE_ID = int(os.getenv("DEV_ROLE_ID"))

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


empty_since = None

########################
### HELPER FUNCTIONS ###
########################

async def no_permission(interaction: discord.Interaction):
    '''Report back insufficient permission.'''
    await interaction.response.send_message(
        "❌ You don't have permission to use this command.",
        ephemeral=True
    )

def has_permission(interaction: discord.Interaction):
    '''Check `MC Player` role permission.'''
    if interaction.user.id == OWNER_ID:
        return True
    if isinstance(interaction.user, discord.Member):
        return any(role.id == ROLE_ID for role in interaction.user.roles)
    return False

def has_dev_permission(interaction: discord.Interaction):
    '''Check `dev` role permission.'''
    if interaction.user.id == OWNER_ID:
        return True
    if isinstance(interaction.user, discord.Member):
        return any(role.id == DEV_ROLE_ID for role in interaction.user.roles)
    return False

async def server_is_not_running(interaction: discord.Interaction):
    await interaction.response.send_message(
        "❌ Minecraft is currently offline.",
        ephemeral=True
    )

#################
### BOT TASKS ###
#################

@tasks.loop(seconds=30)
async def inactivity_monitor():
    global empty_since

    if not await asyncio.to_thread(minecraft.is_server_running):
        empty_since = None
        return

    try:
        # Keep RCON on the main thread
        player_count, player_names = minecraft.get_online_players()

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
                    await notify_channel(
                        "🔴 **Minecraft server has shut down due to inactivity.**"
                    )
                    break

                await asyncio.sleep(2)

            empty_since = None

    except Exception as e:
        print(f"Inactivity monitor error: {e}")
        empty_since = None

@inactivity_monitor.before_loop
async def before_monitor():
    await bot.wait_until_ready()

async def notify_channel(message):
    channel = bot.get_channel(CHANNEL_ID)

    if channel is None:
        channel = await bot.fetch_channel(CHANNEL_ID)

    await channel.send(message)

async def wait_for_server_ready(timeout=180):
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        if not await asyncio.to_thread(minecraft.is_server_running):
            await asyncio.sleep(5)
            continue

        try:
            player_count, player_names = minecraft.get_online_players()
            return True
        except Exception:
            await asyncio.sleep(5)

    return False

@bot.event
async def on_ready():
    await bot.tree.sync()

    if not inactivity_monitor.is_running():
        inactivity_monitor.start()

    print(f"Logged in as {bot.user}")


#############################
### SERVER SLASH COMMANDS ###
#############################

@bot.tree.command(
    name="serverstatus",
    description="Check Minecraft server status"
)
async def serverstatus(interaction: discord.Interaction):
    if not has_permission(interaction):
        return no_permission(interaction)

    if not await asyncio.to_thread(minecraft.is_server_running):
        await interaction.response.send_message(
            "Minecraft server is offline."
        )
        return

    try:
        player_count, player_names = minecraft.get_online_players()

        player_list = "\n".join(
            f"• {name}" for name in player_names
        ) if player_names else "Nobody is online."

        await interaction.response.send_message(
            f"🟢 **Minecraft is online!**\n"
            f"Players: {player_count}\n\n"
            f"**Online players:**\n{player_list}"
        )

    except Exception as e:
        await interaction.response.send_message(
            f"Server is still starting up.",
            ephemeral=True
        )


@bot.tree.command(
    name="startserver",
    description="Start the Minecraft server"
)
async def startserver(interaction: discord.Interaction):
    if not has_permission(interaction):
        return no_permission(interaction)

    if await asyncio.to_thread(minecraft.is_server_running):
        await interaction.response.send_message(
            "Minecraft is already running!"
        )
        return

    await interaction.response.defer()

    try:
        await asyncio.to_thread(minecraft.start_server)

        ready = await wait_for_server_ready()

        if ready:
            await notify_channel(
                "🟢 **Minecraft server is now online!**"
            )
            await interaction.followup.send(
                "Minecraft started successfully!"
            )
        else:
            await interaction.followup.send(
                "Minecraft did not become ready within 3 minutes."
            )

    except Exception as e:
        await interaction.followup.send(
            f"Failed to start Minecraft: {e}"
        )


@bot.tree.command(
    name="serverrules",
    description="Display the Minecraft server rules"
)
async def serverrules(interaction: discord.Interaction):

    rules_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "./info/server_rules.txt"
    )

    try:
        with open(rules_path, "r", encoding="utf-8") as file:
            rules = file.read().strip()

        if not rules:
            await interaction.response.send_message(
                "The server rules file is empty.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"📜 **Minecraft Server Rules**\n\n{rules}"
        )

    except FileNotFoundError:
        await interaction.response.send_message(
            "Could not find server_rules.txt.",
            ephemeral=True
        )


@bot.tree.command(
    name="help",
    description="Show bot commands and server joining instructions"
)
async def help_command(interaction: discord.Interaction):

    # Automatically list registered commands
    command_list = ["These commands can be used when you have the \"MC Player\" role."]

    for command in bot.tree.get_commands():
        if command.name == "help":
            permission = "Everyone"
        elif command.name in ("serverstatus", "startserver"):
            permission = "MC Player role or server owner"
        else:
            permission = "Everyone"

        command_list.append(
            f"**/{command.name}**\n"
            f"{command.description}\n"
            f"*Access: {permission}*"
        )

    # Read joining instructions
    info_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "./info/server_info.txt"
    )

    try:
        with open(info_path, "r", encoding="utf-8") as file:
            server_info = file.read().strip()
    except FileNotFoundError:
        server_info = "Server information file not found."

    # Build Discord embed
    embed = discord.Embed(
        title="🤖 Minecraft Server Help",
        color=discord.Color.green()
    )

    embed.add_field(
        name="📋 Bot Commands",
        value="\n\n".join(command_list)[:1024],
        inline=False
    )

    # Discord embed fields have a 1024-character limit
    # Split longer joining instructions into multiple fields
    chunks = [
        server_info[i:i + 1000]
        for i in range(0, len(server_info), 1000)
    ]

    for index, chunk in enumerate(chunks):
        embed.add_field(
            name="🌍 How to Join" if index == 0 else "How to Join (continued)",
            value=chunk,
            inline=False
        )

    await interaction.response.send_message(embed=embed)


######################
#### DEV COMMANDS ####
######################

@bot.tree.command(
    name="shutdown",
    description="Shut down the Minecraft server (dev only)"
)
async def shutdown(interaction: discord.Interaction):
    if not has_dev_permission(interaction):
        return no_permission(interaction)

    if not minecraft.is_server_running():
        return server_is_not_running(interaction)

    await interaction.response.send_message(
        "⚠️ **Are you sure you want to shut down Minecraft?**\n"
        "The world will be saved before the server stops.",
        view=ShutdownConfirmView(),
        ephemeral=True
    )


def get_spark_health_url(timeout=5):
    log_file = Path("/opt/minecraft/server/logs/latest.log")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            with log_file.open("r") as f:
                lines = f.readlines()

            for line in reversed(lines):
                match = re.search(r"https://spark\.lucko\.me/\S+", line)
                if match:
                    return match.group(0)

        except OSError:
            pass

        time.sleep(0.5)

    return None


@bot.tree.command(name="sparkhealth", description="Show Minecraft server health (dev only)")
@discord.app_commands.default_permissions()
async def sparkhealth(interaction: discord.Interaction):
    if not has_dev_permission(interaction):
        return no_permission(interaction)

    if not minecraft.is_server_running():
        return server_is_not_running(interaction)

    await interaction.response.defer(ephemeral=True)

    try:
        minecraft.send_command("spark health")
        url = get_spark_health_url()

        if url:
            await interaction.followup.send(
                f"📊 **Live Spark Health Dashboard:**\n{url}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❌ Spark generated no dashboard URL. Check the server logs.",
                ephemeral=True
            )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to run Spark health: `{e}`",
            ephemeral=True
        )


@bot.tree.command(
    name="godtext",
    description="Send a divine announcement to all Minecraft players (dev only)"
)
async def godtext(interaction: discord.Interaction, message: str):
    if not has_dev_permission(interaction):
        return no_permission(interaction)

    if not minecraft.is_server_running():
        return server_is_not_running(interaction)

    if len(message) > 500:
        await interaction.response.send_message(
            "❌ Your message is too long. Maximum length is 500 characters.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    try:
        tellraw_message = {
            "text": "",
            "extra": [
                {
                    "text": "[GOD] ",
                    "color": "gold",
                    "bold": True
                },
                {
                    "text": message,
                    "color": "yellow"
                }
            ]
        }

        command = f"tellraw @a {json.dumps(tellraw_message, ensure_ascii=False)}"
        minecraft.send_command(command)

        await interaction.followup.send(
            f"Divine announcement delivered!\n> {message}",
            ephemeral=True
        )

    except Exception as e:
        await interaction.followup.send(
            f"❌ Failed to send godly message: `{e}`",
            ephemeral=True
        )


### WHITELIST ###

whitelist_group = discord.app_commands.Group(
    name="whitelist",
    description="Manage the Minecraft whitelist (dev only)"
)


@whitelist_group.command(name="add", description="Add a player to the whitelist")
async def whitelist_add(interaction: discord.Interaction, playername: str):
    if not has_dev_permission(interaction):
        return no_permission(interaction)

    if not minecraft.is_server_running():
        return server_is_not_running(interaction)

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
async def whitelist_remove(interaction: discord.Interaction, playername: str):
    if not has_dev_permission(interaction):
        return no_permission(interaction)

    if not minecraft.is_server_running():
        return server_is_not_running(interaction)

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
async def whitelist_list(interaction: discord.Interaction):
    if not has_dev_permission(interaction):
        return no_permission(interaction)

    if not minecraft.is_server_running():
        return server_is_not_running(interaction)

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


### SHUTDOWNCONFIRMVIEW ###

class ShutdownConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(
        label="Confirm shutdown",
        style=discord.ButtonStyle.danger,
        emoji="🛑"
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        if not has_dev_permission(interaction):
            return no_permission(interaction)

        if not minecraft.is_server_running():
            await interaction.response.edit_message(
                content="ℹ️ Minecraft is already offline.",
                view=None
            )
            return

        try:
            minecraft.stop_server()

            await interaction.response.edit_message(
                content="🛑 **Shutdown command sent!** Minecraft is saving the world and shutting down.",
                view=None
            )

        except Exception as e:
            await interaction.response.edit_message(
                content=f"❌ Failed to shut down: `{e}`",
                view=None
            )

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.secondary,
        emoji="✖️"
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        await interaction.response.edit_message(
            content="✅ Shutdown cancelled.",
            view=None
        )

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


bot.tree.add_command(whitelist_group)
bot.run(TOKEN)
