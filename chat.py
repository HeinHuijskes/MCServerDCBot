import re
from pathlib import Path

# "[17:53:55] [Async Chat Thread - #0/INFO]: <Steve> hello"  (optionally "[Not Secure] ")
_LINE = re.compile(r"^\[[\d:]+\] \[[^\]]+/INFO\]: (?P<msg>.*)$")
_CHAT = re.compile(r"^(?:\[Not Secure\] )?<(?P<name>[^>]+)> (?P<text>.*)$")
_JOIN = re.compile(r"^(?:System chat: )?(?P<name>\S+) joined the game$")
_LEAVE = re.compile(r"^(?:System chat: )?(?P<name>\S+) left the game$")
_ADVANCEMENT = re.compile(
    r"^(?:System chat: )?(?P<name>\S+) has (?P<verb>made the advancement|completed the challenge|reached the goal) \[(?P<title>.+)\]$"
)
_SYSTEM = re.compile(r"^System chat: (?P<text>.+)$")
# Minecraft's death messages: "<name> <phrase> ...". Add a phrase here if a death shows up as ℹ️.
_DEATH_PHRASES = [
    "died", "drowned", "blew up", "burned to death", "starved to death", "froze to death",
    "suffocated", "withered away", "fell", "hit the ground", "tried to swim in lava",
    "walked into", "went up in flames", "went off with a bang", "experienced kinetic energy",
    "discovered the floor was lava", "left the confines of this world",
    "didn't want to live in the same world as",
    "was (?:shot|slain|killed|fireballed|pummeled|impaled|squashed|squished|stung|poked|pricked"
    "|blown|roasted|doomed|obliterated|smashed|burned|frozen|knocked|struck|skewered)",
]
_DEATH = re.compile(r"^(?P<name>\S+) (?P<rest>(?:" + "|".join(_DEATH_PHRASES) + r")\b.*)$")
# Command feedback shown to admins: "[Sender: Granted the advancement ...]"
_COMMAND_FEEDBACK = re.compile(r"^\[[^\]:]+: .*\]$")


def parse_log_line(line: str):
    """Return ("chat", name, text), ("join", name), ("leave", name),
    ("advancement", name, verb, title), ("death", name, rest),
    ("system", text) or None."""
    match = _LINE.match(line)
    if not match:
        return None
    msg = match["msg"]

    if m := _CHAT.match(msg):
        return ("chat", m["name"], m["text"])
    if m := _JOIN.match(msg):
        return ("join", m["name"])
    if m := _LEAVE.match(msg):
        return ("leave", m["name"])
    if m := _ADVANCEMENT.match(msg):
        return ("advancement", m["name"], m["verb"], m["title"])
    if m := _SYSTEM.match(msg):
        text = m["text"]
        if text.startswith("[Discord] "):  # our own relayed messages
            return None
        if _COMMAND_FEEDBACK.match(text):  # feedback from commands
            return None
        if d := _DEATH.match(text):
            return ("death", d["name"], d["rest"])
        return ("system", text)
    return None


class LogTailer:
    """Returns only the complete lines added to a log file since the last call."""

    def __init__(self, path):
        self.path = Path(path)
        self.offset = None  # None = first call: skip existing history
        self.inode = None

    def read_new_lines(self):
        try:
            st = self.path.stat()
        except OSError:
            return []

        if self.offset is None:
            self.offset, self.inode = st.st_size, st.st_ino
            return []

        # New file (server restarted / log rotated): read it from the start
        if st.st_ino != self.inode or st.st_size < self.offset:
            self.offset, self.inode = 0, st.st_ino

        if st.st_size == self.offset:
            return []

        with self.path.open("rb") as f:
            f.seek(self.offset)
            data = f.read()

        end = data.rfind(b"\n")
        if end == -1:  # only a partial line so far; wait for the rest
            return []

        self.offset += end + 1
        return data[:end].decode("utf-8", errors="replace").splitlines()