"""Optional SFX adapter. The game works silently until WAV files are added."""

import shutil
import subprocess
import sys
import time
from pathlib import Path


class AudioManager:
    EVENTS = ("shoot", "explosion", "hit", "pickup", "powerup", "missile", "victory", "defeat")

    def __init__(self, directory: Path):
        self.files = {name: directory / f"{name}.wav" for name in self.EVENTS}
        self.enabled = True
        self.last_played = {}
        self.process = None
        self.player = (shutil.which("afplay") if sys.platform == "darwin" else
                       shutil.which("paplay") or shutil.which("aplay"))
        self.available = any(p.is_file() for p in self.files.values()) and (
            sys.platform == "win32" or bool(self.player))

    def play(self, event: str):
        path = self.files.get(event)
        now = time.monotonic()
        if not self.enabled or not self.available or not path or not path.is_file():
            return
        if now - self.last_played.get(event, 0) < (.12 if event == "shoot" else .05):
            return
        self.last_played[event] = now
        try:
            if sys.platform == "win32":
                import winsound
                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            elif self.player:
                if self.process and self.process.poll() is None:
                    if event == "shoot":
                        return
                    self.process.terminate()
                self.process = subprocess.Popen([self.player, str(path)],
                                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, RuntimeError):
            pass  # An unavailable audio device must never interrupt a run.

    def close(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
        if sys.platform == "win32" and self.available:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
