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
from whitelist import *
from constants import *


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("DISCORD_USER_ID", "0"))
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
ROLE_ID = int(os.getenv("DISCORD_ROLE_ID"))
DEV_ROLE_ID = int(os.getenv("DEV_ROLE_ID"))


## PATHS ##
main_path = "~/Projects/MCServerDCBOT"
rules_path = f"{main_path}/info/server_rules.txt"
info_path = f"{main_path}/info/server_info.txt"


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


empty_since = None

########################
### HELPER FUNCTIONS ###
########################

async def send_message(interaction: discord.Interaction, message: str, **kwargs):
    '''Send a message back'''
    await interaction.response.send_message(message, **kwargs)

async def follow_up(interaction: discord.Interaction, message: str):
    '''Follow up on an interaction'''
    await interaction.followup.send(message)

async def no_permission(interaction: discord.Interaction):
    '''Report back insufficient permission.'''
    await send_message(interaction, MSG_NO_PERMISSION, ephemeral=True)

async def server_is_not_running(interaction: discord.Interaction):
    await send_message(interaction, MSG_OFFLINE, ephemeral=True)

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
            _, _ = minecraft.get_online_players()
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


@bot.tree.command(
    name="startserver",
    description="Start the Minecraft server"
)
async def startserver(interaction: discord.Interaction):
    if not has_permission(interaction):
        return no_permission(interaction)

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


@bot.tree.command(
    name="serverrules",
    description="Display the Minecraft server rules"
)
async def serverrules(interaction: discord.Interaction):
    try:
        with open(rules_path, "r", encoding="utf-8") as file:
            rules = file.read().strip()
    except FileNotFoundError:
        rules = ""
    send_message(interaction, f"{MSG_RULES}{rules}")


@bot.tree.command(
    name="help",
    description="Show bot commands and server joining instructions"
)
async def help_command(interaction: discord.Interaction):
    command_list = []
    for command in bot.tree.get_commands():
        if "(dev only)" in command.description:
            continue

        command_list.append(
            f"**/{command.name}**\n"
            f"{command.description}"
        )

    try:
        with open(info_path, "r", encoding="utf-8") as file:
            server_info = file.read().strip()
    except FileNotFoundError:
        server_info = ""

    # Build Discord embed
    embed = discord.Embed(title=MSG_HELP, color=discord.Color.green())

    embed.add_field(
        name="📋 Bot Commands",
        value="\n\n".join(command_list)[:1024],
        inline=False
    )

    embed.add_field(name="🌍 How to Join", value=server_info, inline=False)
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
