import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

_EPOCH = datetime.fromtimestamp(0, timezone.utc)  # used when a completion time is unknown
_ADV_PATH = re.compile(r"^data/minecraft/advancements?/(?P<id>.+)\.json$")
_vanilla = None  # cache: (translations, set of valid advancement ids)


def level_name(server_dir: Path) -> str:
    try:
        for line in (server_dir / "server.properties").read_text(encoding="utf-8").splitlines():
            if line.startswith("level-name="):
                return line.split("=", 1)[1].strip() or "world"
    except OSError:
        pass
    return "world"


def advancement_dir(server_dir: Path):
    """Newer versions use world/players/advancements, older ones world/advancements."""
    world = server_dir / level_name(server_dir)
    for sub in ("players/advancements", "advancements"):
        if (world / sub).is_dir():
            return world / sub
    return None


def load_names(server_dir: Path) -> dict:
    """{uuid: player name}, from usercache.json and whitelist.json."""
    names = {}
    for filename in ("usercache.json", "whitelist.json"):  # whitelist last, so it wins
        try:
            for entry in json.loads((server_dir / filename).read_text(encoding="utf-8")):
                names[entry["uuid"].lower()] = entry["name"]
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return names


def load_vanilla(server_dir: Path):
    """Read titles and the list of real advancements from the server jar (cached)."""
    global _vanilla
    if _vanilla is not None:
        return _vanilla

    jars = (list(server_dir.glob("cache/mojang_*.jar"))
            + list(server_dir.glob("versions/**/*.jar"))
            + list(server_dir.glob("*.jar")))
    for jar in jars:
        try:
            with zipfile.ZipFile(jar) as z:
                names = z.namelist()
                if "assets/minecraft/lang/en_us.json" not in names:
                    continue
                lang = json.loads(z.read("assets/minecraft/lang/en_us.json"))
                valid = set()
                for n in names:
                    m = _ADV_PATH.match(n)
                    if not m or m["id"].startswith("recipes/"):
                        continue
                    data = json.loads(z.read(n))
                    if "display" in data and "parent" in data:  # skips roots and hidden ones
                        valid.add("minecraft:" + m["id"])
                _vanilla = (lang, valid)
                return _vanilla
        except (OSError, zipfile.BadZipFile, KeyError, ValueError):
            continue

    _vanilla = ({}, set())  # jar not found: fall back to prettified ids, unknown total
    return _vanilla


def total_count(server_dir: Path) -> int:
    """Number of obtainable advancements, or 0 if unknown."""
    return len(load_vanilla(server_dir)[1])


def get_title(server_dir: Path, adv_id: str) -> str:
    lang = load_vanilla(server_dir)[0]
    key = "advancements." + adv_id.split(":", 1)[-1].replace("/", ".") + ".title"
    return lang.get(key) or adv_id.split("/")[-1].replace("_", " ").title()


def _parse_time(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")
    except (ValueError, TypeError):
        return _EPOCH


def _read_completed(path: Path, valid: set) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    done = {}
    for adv_id, entry in data.items():
        if not isinstance(entry, dict) or not entry.get("done"):
            continue  # also skips the "DataVersion" number
        if valid:
            if adv_id not in valid:
                continue
        elif (not adv_id.startswith("minecraft:") or adv_id.startswith("minecraft:recipes/")
              or adv_id.endswith("/root")):
            continue
        done[adv_id] = max((_parse_time(t) for t in entry.get("criteria", {}).values()), default=_EPOCH)
    return done


def load_all(server_dir: Path) -> dict:
    """{player name: {advancement id: completion time}} for every player with a save file."""
    adv_dir = advancement_dir(server_dir)
    if adv_dir is None:
        raise FileNotFoundError("Advancements folder not found")

    names = load_names(server_dir)
    valid = load_vanilla(server_dir)[1]
    result = {}
    for file in adv_dir.glob("*.json"):
        uuid = file.stem.lower()
        try:
            result[names.get(uuid, uuid[:8])] = _read_completed(file, valid)
        except (OSError, ValueError):
            continue
    return result
