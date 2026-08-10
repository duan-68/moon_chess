"""棋盘模型：3×3 网格，落子/移除/判胜"""

from __future__ import annotations

from typing import Optional

ROWS = 3
COLS = 3


class Board:
    """3×3 月亮棋棋盘。"""

    def __init__(self) -> None:
        self._grid: list[list[Optional[int]]] = [
            [None for _ in range(COLS)] for _ in range(ROWS)
        ]

    @property
    def grid(self) -> list[list[Optional[int]]]:
        return self._grid

    def cell(self, row: int, col: int) -> Optional[int]:
        """返回指定格子的玩家编号，None 表示空格。"""
        return self._grid[row][col]

    def is_empty(self, row: int, col: int) -> bool:
        """检查格子是否为空。"""
        return self._grid[row][col] is None

    def place(self, row: int, col: int, player_id: int) -> None:
        """在指定位置放置棋子。"""
        self._grid[row][col] = player_id

    def remove(self, row: int, col: int) -> None:
        """清除指定位置的棋子。"""
        self._grid[row][col] = None

    def check_win(self) -> Optional[int]:
        """检查是否有玩家三连。返回获胜玩家 ID，无则返回 None。"""
        lines = self._all_lines()
        for line in lines:
            if line[0] is not None and line[0] == line[1] == line[2]:
                return line[0]
        return None

    def is_full(self) -> bool:
        """检查棋盘是否已满。"""
        return all(
            self._grid[r][c] is not None for r in range(ROWS) for c in range(COLS)
        )

    def empty_cells(self) -> list[tuple[int, int]]:
        """返回所有空格子的坐标列表。"""
        return [
            (r, c)
            for r in range(ROWS)
            for c in range(COLS)
            if self._grid[r][c] is None
        ]

    def _all_lines(self) -> list[list[Optional[int]]]:
        """收集所有可能的三连线（8条）。"""
        rows = [[self._grid[r][c] for c in range(COLS)] for r in range(ROWS)]
        cols = [[self._grid[r][c] for r in range(ROWS)] for c in range(COLS)]
        diag1 = [[self._grid[i][i] for i in range(ROWS)]]
        diag2 = [[self._grid[i][COLS - 1 - i] for i in range(ROWS)]]
        return rows + cols + diag1 + diag2

    def __str__(self) -> str:
        lines = []
        for r in range(ROWS):
            row_cells = []
            for c in range(COLS):
                v = self._grid[r][c]
                row_cells.append("·" if v is None else str(v))
            lines.append(" ".join(row_cells))
        return "\n".join(lines)
