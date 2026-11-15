import re
from pathlib import Path

# "[17:53:55] [Async Chat Thread - #0/INFO]: <Steve> hello"  (optionally "[Not Secure] ")
_LINE = re.compile(r"^\[[\d:]+\] \[[^\]]+/INFO\]: (?P<msg>.*)$")
_CHAT = re.compile(r"^(?:\[Not Secure\] )?<(?P<name>[^>]+)> (?P<text>.*)$")
_JOIN = re.compile(r"^(?P<name>\S+) joined the game$")
_LEAVE = re.compile(r"^(?P<name>\S+) left the game$")


def parse_log_line(line: str):
    """Return ("chat", name, text), ("join", name), ("leave", name) or None."""
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