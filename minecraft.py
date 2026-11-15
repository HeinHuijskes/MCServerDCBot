import os
import subprocess
from mcrcon import MCRcon
from dotenv import load_dotenv

load_dotenv()

RCON_HOST = os.getenv("RCON_HOST", "127.0.0.1")
RCON_PORT = int(os.getenv("RCON_PORT", "25575"))
RCON_PASSWORD = os.getenv("RCON_PASSWORD")

SERVICE_NAME = "minecraft.service"


def send_command(command):
    """Send a command to Minecraft through RCON."""
    if not RCON_PASSWORD:
        raise RuntimeError("RCON_PASSWORD is not configured")

    with MCRcon(
        RCON_HOST,
        RCON_PASSWORD,
        port=RCON_PORT
    ) as rcon:
        return rcon.command(command)


def get_online_players():
    """Return the number of online players and their usernames."""
    response = send_command("list")

    try:
        player_part = response.split(":", 1)[1].strip()

        if not player_part:
            return 0, []

        players = [name.strip() for name in player_part.split(",") if name.strip()]

        return len(players), players

    except (ValueError, IndexError):
        raise RuntimeError(f"Unexpected RCON response: {response}")


def is_server_running():
    """Check whether the Minecraft systemd service is active."""
    result = subprocess.run(
        ["systemctl", "is-active", "--quiet", SERVICE_NAME]
    )
    return result.returncode == 0


def start_server():
    """Start the Minecraft systemd service."""
    subprocess.run(
        ["sudo", "systemctl", "start", SERVICE_NAME],
        check=True
    )


def stop_server():
    """Gracefully stop Minecraft through RCON."""
    send_command("stop")
