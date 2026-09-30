"""Small contract shared by heavy and lightweight page processors."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class PageAdapter(Protocol):
    @property
    def stage_name(self) -> str: ...

    @property
    def revision(self) -> str: ...

    @property
    def heavy(self) -> bool: ...

    def load(self) -> None: ...

    def run_page(self, page: Path) -> dict[str, Any]: ...

    def unload(self) -> None: ...

