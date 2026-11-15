import json
from pathlib import Path

from .advancements import level_name, load_names

TICKS_PER_SECOND = 20


def stats_dir(server_dir: Path):
    """Newer versions use world/players/stats, older ones world/stats."""
    world = server_dir / level_name(server_dir)
    for sub in ("players/stats", "stats"):
        if (world / sub).is_dir():
            return world / sub
    return None


def format_duration(seconds: float) -> str:
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if days or hours:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)


def load_playtimes(server_dir: Path) -> dict:
    """{player name: seconds played} for every player with a stats file."""
    folder = stats_dir(server_dir)
    if folder is None:
        raise FileNotFoundError("Stats folder not found")

    names = load_names(server_dir)
    result = {}
    for file in folder.glob("*.json"):
        try:
            custom = json.loads(file.read_text(encoding="utf-8")).get("stats", {}).get("minecraft:custom", {})
        except (OSError, ValueError, AttributeError):
            continue
        # "play_one_minute" is the pre-1.17 name for the same counter (it counts ticks)
        ticks = custom.get("minecraft:play_time", custom.get("minecraft:play_one_minute", 0))
        result[names.get(file.stem.lower(), file.stem[:8])] = ticks / TICKS_PER_SECOND
    return result
