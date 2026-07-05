from __future__ import annotations

from abc import ABC, abstractmethod


class State(ABC):
    """显式应用状态的基类。"""

    @abstractmethod
    def name(self) -> str:
        """返回供 UI 或调试使用的稳定状态名。"""
        raise NotImplementedError
