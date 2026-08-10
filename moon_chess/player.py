"""玩家模型：FIFO 队列记录落子历史（maxlen=3）"""

from __future__ import annotations

from collections import deque
from typing import Optional


class Player:
    """月亮棋玩家。

    维护最多 3 步的落子队列，当落第 4 子时最早棋子自动淘汰。
    """

    def __init__(self, player_id: int, name: str) -> None:
        self.id = player_id
        self.name = name
        self._moves: deque[tuple[int, int]] = deque()

    @property
    def piece_count(self) -> int:
        """当前棋盘上的棋子数。"""
        return len(self._moves)

    @property
    def moves(self) -> list[tuple[int, int]]:
        """返回当前棋盘上的棋子坐标列表（按落子顺序）。"""
        return list(self._moves)

    def record_move(self, row: int, col: int) -> Optional[tuple[int, int]]:
        """记录一次落子。

        返回被淘汰的最早棋子坐标，若棋子数未超 3 则返回 None。
        """
        removed: Optional[tuple[int, int]] = None
        if len(self._moves) >= 3:
            removed = self._moves[0]
        self._moves.append((row, col))
        while len(self._moves) > 3:
            self._moves.popleft()
        return removed

    def reset(self) -> None:
        """重置玩家状态。"""
        self._moves.clear()
