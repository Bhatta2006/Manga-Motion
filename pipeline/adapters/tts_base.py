"""Future voice engines plug into this contract; no engine is loaded in M0b."""
from pathlib import Path
from typing import Protocol


class VoiceAdapter(Protocol):
    revision: str
    heavy: bool

    def load(self) -> None: ...
    def synthesize(self, text: str, voice_id: str, emotion: str,
                   intensity: float, lang: str, output: Path) -> Path: ...
    def unload(self) -> None: ...
