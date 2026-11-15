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

## ENV VARIABLES ##
TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = int(os.getenv("DISCORD_USER_ID", "0"))
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
ROLE_ID = int(os.getenv("DISCORD_ROLE_ID"))
DEV_ROLE_ID = int(os.getenv("DEV_ROLE_ID"))

## PATHS ##
main_path = "~/Projects/MCServerDCBOT"
rules_path = f"{main_path}/info/server_rules.txt"
info_path = f"{main_path}/info/server_info.txt"


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


def dev_only(command):
    '''Assign dev-only attribute, mainly for /help display purposes.'''
    command.dev_only = True
    return command


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