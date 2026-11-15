import discord
import minecraft
from constants import *

from dotenv import load_dotenv
from pathlib import Path
import asyncio
import time
import os
import re

load_dotenv()

REQUIRED_ENV = [
    "DISCORD_TOKEN", "DISCORD_USER_ID", "DISCORD_CHANNEL_ID",
    "DISCORD_ROLE_ID", "DEV_ROLE_ID", "RCON_PASSWORD",
]
missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
if missing:
    raise SystemExit(f"Missing required .env variables: {', '.join(missing)}")

## ENV VARIABLES ##
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("DISCORD_USER_ID", "0"))
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
ROLE_ID = int(os.getenv("DISCORD_ROLE_ID"))
DEV_ROLE_ID = int(os.getenv("DEV_ROLE_ID"))

## PATHS ##
main_path = Path("~/Projects/MCServerDCBot").expanduser()
rules_path = main_path / "info" / "server_rules.txt"
info_path = main_path / "info" / "server_info.txt"


########################
### HELPER FUNCTIONS ###
########################


async def send_message(interaction: discord.Interaction, message: str, **kwargs):
    '''Send a message back'''
    await interaction.response.send_message(message, **kwargs)


async def follow_up(interaction: discord.Interaction, message: str):
    '''Follow up on an interaction'''
    await interaction.followup.send(message, ephemeral=True)


async def no_permission(interaction: discord.Interaction):
    '''Report back insufficient permission.'''
    await send_message(interaction, MSG_NO_PERMISSION, ephemeral=True)


async def server_is_running(interaction: discord.Interaction):
    '''Pre-command check to see if the server is up and running.'''
    if not minecraft.is_server_running():
        await send_message(interaction, MSG_OFFLINE)
        return False
    return True    


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


def is_dev_only(command) -> bool:
    '''True if the command, or any group above it, requires the dev role.'''
    while command is not None:
        if isinstance(command, DevGroup):
            return True
        if has_dev_permission in getattr(command, "checks", []):
            return True
        command = command.parent
    return False


async def server_is_running(interaction: discord.Interaction):
    '''Pre-command check to see if the server is up and running.'''
    if not await asyncio.to_thread(minecraft.is_server_running):
        raise ServerOffline()
    return True


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


LOG_FILE = Path("/opt/minecraft/server/logs/latest.log")


def get_log_size() -> int:
    try:
        return LOG_FILE.stat().st_size
    except OSError:
        return 0


def get_spark_health_url(offset: int = 0, timeout: int = 5):
    '''Find a Spark URL written to the log after `offset` bytes.'''
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        try:
            # If the log shrank, it was rotated: read the new file from the start
            start = offset if LOG_FILE.stat().st_size >= offset else 0

            with LOG_FILE.open("rb") as f:
                f.seek(start)
                text = f.read().decode("utf-8", errors="ignore")

            matches = re.findall(r"https://spark\.lucko\.me/\S+", text)
            if matches:
                return matches[-1]
        except OSError:
            pass

        time.sleep(0.5)

    return None


def get_tellraw_message(message):
    return {
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


class DevGroup(discord.app_commands.Group):
    '''A command group whose subcommands all require the dev role.'''
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return has_dev_permission(interaction)


class ServerOffline(discord.app_commands.CheckFailure):
    pass


class ShutdownConfirmView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.interaction = interaction  # the original /shutdown interaction

    @discord.ui.button(label="Confirm shutdown", style=discord.ButtonStyle.danger, emoji="🛑")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()  # prevents on_timeout from overwriting the result later

        if not has_dev_permission(interaction):
            return await no_permission(interaction)

        if not await asyncio.to_thread(minecraft.is_server_running):
            await interaction.response.edit_message(content="ℹ️ Minecraft is already offline.", view=None)
            return

        # Respond immediately, then do the slow RCON call
        await interaction.response.edit_message(content="⏳ Sending shutdown command...", view=None)
        try:
            await asyncio.to_thread(minecraft.stop_server)
            await interaction.edit_original_response(
                content="🛑 **Shutdown command sent!** Minecraft is saving the world and shutting down."
            )
        except Exception as e:
            await interaction.edit_original_response(content=f"❌ Failed to shut down: `{e}`")

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content="✅ Shutdown cancelled.", view=None)

    async def on_timeout(self):
        try:
            await self.interaction.edit_original_response(content="⌛ Shutdown confirmation expired.", view=None)
        except discord.HTTPException:
            pass
