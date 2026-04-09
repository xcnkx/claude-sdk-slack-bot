from __future__ import annotations

from pathlib import Path


class MemoryStore:
    def __init__(self, memory_dir: Path) -> None:
        self._dir = memory_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / "channels").mkdir(exist_ok=True)

    @property
    def workspace_path(self) -> Path:
        return self._dir / "workspace.md"

    def channel_path(self, channel_id: str) -> Path:
        return self._dir / "channels" / f"{channel_id}.md"

    def load_workspace(self) -> str:
        if self.workspace_path.exists():
            return self.workspace_path.read_text()
        return ""

    def load_channel(self, channel_id: str) -> str:
        path = self.channel_path(channel_id)
        if path.exists():
            return path.read_text()
        return ""
