from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ActionResult:
    ok: bool
    message: str = ""
    payload: Any | None = None
