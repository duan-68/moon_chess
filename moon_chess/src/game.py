"""游戏控制器：回合管理、落子验证、胜负判定"""

from __future__ import annotations

from typing import Optional

from moon_chess.src.board import Board
from moon_chess.src.player import Player


class Game:
    """月亮棋游戏控制器。

    管理回合循环，执行「落子 → 淘汰 → 判胜 → 切换回合」的结算流程。
    """

    def __init__(self, player1_name: str = "🌕 明月", player2_name: str = "🌑 暗月") -> None:
        self.board = Board()
        self.players = (Player(1, player1_name), Player(2, player2_name))
        self.current_idx = 0
        self.move_count = 0
        self.winner: Optional[int] = None
        self._game_over = False

    @property
    def current_player(self) -> Player:
        return self.players[self.current_idx]

    @property
    def opponent(self) -> Player:
        return self.players[1 - self.current_idx]

    @property
    def is_over(self) -> bool:
        return self._game_over

    def make_move(self, row: int, col: int) -> Optional[int]:
        """执行一步落子。

        结算顺序：验证 → 落子 → 淘汰最早棋子 → 判胜 → 切回合

        返回获胜玩家 ID，游戏未结束时返回 None。
        若落子非法则抛出 ValueError。
        """
        if self._game_over:
            raise ValueError("游戏已结束")

        if not (0 <= row < 3 and 0 <= col < 3):
            raise ValueError(f"坐标 ({row}, {col}) 超出棋盘范围")

        if not self.board.is_empty(row, col):
            raise ValueError(f"格子 ({row}, {col}) 已被占据")

        player = self.current_player

        # 1. 落子
        self.board.place(row, col, player.id)

        # 2. 记录落子，若超过 3 枚则淘汰最早棋子
        removed = player.record_move(row, col)
        if removed is not None:
            self.board.remove(removed[0], removed[1])

        # 3. 判定胜负
        self.winner = self.board.check_win()

        # 4. 切换回合
        self.move_count += 1
        if self.winner is not None:
            self._game_over = True
        else:
            self.current_idx = 1 - self.current_idx

        return self.winner

    def is_legal_move(self, row: int, col: int) -> bool:
        """检查落子是否合法。"""
        return 0 <= row < 3 and 0 <= col < 3 and self.board.is_empty(row, col)

    def legal_moves(self) -> list[tuple[int, int]]:
        """返回当前所有合法落子坐标。"""
        return self.board.empty_cells()

    def reset(self) -> None:
        """重置游戏到初始状态。"""
        self.board = Board()
        for p in self.players:
            p.reset()
        self.current_idx = 0
        self.move_count = 0
        self.winner = None
        self._game_over = False
