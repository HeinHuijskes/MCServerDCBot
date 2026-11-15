import discord
from . import minecraft, PROJECT_ROOT
from .constants import *

from pathlib import Path
import urllib.parse
import aiohttp
import logging
import asyncio
import time
import os
import re


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
CHAT_CHANNEL_ID = int(os.getenv("DISCORD_CHAT_CHANNEL_ID", "0"))

## PATHS ##
RULES_PATH = PROJECT_ROOT / "info" / "server_rules.txt"
INFO_PATH = PROJECT_ROOT / "info" / "server_info.txt"
SERVER_DIR = Path("/opt/minecraft/server")
LOG_FILE = Path("/opt/minecraft/server/logs/latest.log")


## CHAT LOGGING WEBHOOK ##
log = logging.getLogger("mcbot")   # same logger as in bot.py, matched by name
CHAT_WEBHOOK_NAME = "Minecraft"   # name shown for server events (joins, deaths, ...)
NO_PINGS = discord.AllowedMentions.none()   # stops "@everyone" typed in-game from pinging
chat_webhook = None
webhooks_disabled = False
head_emojis = {}
head_emojis_loaded = False


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


def head_url(player: str, size: int = 128) -> str:
    return f"https://mc-heads.net/avatar/{urllib.parse.quote(player)}/{size}"


def emoji_name(player: str) -> str:
    # Discord emoji names: 2-32 chars, letters/digits/underscores only
    return "mc_" + re.sub(r"[^A-Za-z0-9_]", "_", player)[:28]


async def get_head_emoji(client, player: str) -> str:
    '''Return the player's head as an emoji string, uploading it on first use. "" on failure.'''
    global head_emojis_loaded
    try:
        if not head_emojis_loaded:
            for e in await client.fetch_application_emojis():
                head_emojis[e.name] = e
            head_emojis_loaded = True

        name = emoji_name(player)
        if name not in head_emojis:
            async with aiohttp.ClientSession() as session:
                async with session.get(head_url(player, 64), timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status != 200:
                        return ""
                    image = await resp.read()
            head_emojis[name] = await client.create_application_emoji(name=name, image=image)

        return str(head_emojis[name])
    except Exception:
        log.warning("Couldn't get head emoji for %s", player, exc_info=True)
        return ""

async def get_chat_webhook(channel):
    global chat_webhook
    if chat_webhook is None:
        for hook in await channel.webhooks():
            if hook.name == CHAT_WEBHOOK_NAME and hook.user and hook.user.id == channel.guild.me.id:
                chat_webhook = hook
                break
        else:
            chat_webhook = await channel.create_webhook(name=CHAT_WEBHOOK_NAME)
    return chat_webhook


async def send_relay(channel, plain, content=None, username=None, avatar=None):
    """Send with a custom name/avatar. Falls back to a plain bot message if that fails."""
    global webhooks_disabled
    if not webhooks_disabled:
        try:
            hook = await get_chat_webhook(channel)
            kwargs = {"allowed_mentions": NO_PINGS}
            if username:
                kwargs["username"] = username
            if avatar:
                kwargs["avatar_url"] = avatar
            await hook.send(content or plain, **kwargs)
            return
        except discord.Forbidden:
            webhooks_disabled = True
            log.warning("Missing Manage Webhooks permission; using plain bot messages instead")
        except discord.HTTPException:
            log.warning("Webhook send failed; falling back to a plain message", exc_info=True)
    await channel.send(plain, allowed_mentions=NO_PINGS)


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


class PlayerGroup(discord.app_commands.Group):
    '''A command group whose subcommands require the MC Player role.'''
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return has_permission(interaction)


class ServerOffline(discord.app_commands.CheckFailure):
    pass


class ShutdownConfirmView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=60)
        self.interaction = interaction  # the original /shutdown interaction

    @discord.ui.button(label="Confirm shutdown", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()  # prevents on_timeout from overwriting the result later

        if not has_dev_permission(interaction):
            return await no_permission(interaction)

        if not await asyncio.to_thread(minecraft.is_server_running):
            await interaction.response.edit_message(content=MSG_OFFLINE, view=None)
            return

        await interaction.response.edit_message(content=MSG_SHUT_CMD, view=None)
        try:
            minecraft.stop_server()
            await interaction.edit_original_response(
                content=MSG_SHUTTING
            )
        except Exception as e:
            await interaction.edit_original_response(content=MSG_FAIL(e))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.response.edit_message(content=MSG_NO_SHUT, view=None)

    async def on_timeout(self):
        try:
            await self.interaction.edit_original_response(content="⌛ Shutdown confirmation expired.", view=None)
        except discord.HTTPException:
            pass
