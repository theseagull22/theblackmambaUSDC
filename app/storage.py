from __future__ import annotations

import json
from pathlib import Path

from app.state import BotState


class JsonStateStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> BotState:
        if not self.path.exists():
            return BotState()
        data = json.loads(self.path.read_text())
        return BotState.from_dict(data)

    def save(self, state: BotState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state.to_dict(), indent=2, sort_keys=True))
