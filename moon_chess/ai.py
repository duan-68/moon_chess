"""AI 对手"""

from __future__ import annotations

import random
from typing import Optional

from moon_chess.board import Board

INF = 1_000_000


class MoonChessAI:
    """月亮棋 AI。

    简单模式：贪心 + 随机
    困难模式：Minimax + Alpha-Beta 剪枝（深度 4）
    """

    def __init__(self, player_id: int, difficulty: str = "hard") -> None:
        self.player_id = player_id
        self.opponent_id = 3 - player_id
        self.difficulty = difficulty

    def choose_move(
        self,
        board: Board,
        my_moves: list[tuple[int, int]],
        opp_moves: list[tuple[int, int]],
    ) -> tuple[int, int]:
        empty = board.empty_cells()
        if not empty:
            raise ValueError("棋盘已满，无法落子")

        if self.difficulty == "simple":
            return self._choose_simple(board, empty)
        else:
            return self._choose_hard(board, my_moves, opp_moves)

    # ── 简单模式：贪心 + 随机 ──────────────────────────

    def _choose_simple(
        self, board: Board, empty: list[tuple[int, int]]
    ) -> tuple[int, int]:
        # 能否一步获胜
        for r, c in empty:
            board.place(r, c, self.player_id)
            winner = board.check_win()
            board.remove(r, c)
            if winner == self.player_id:
                return (r, c)
        # 封堵对手
        for r, c in empty:
            board.place(r, c, self.opponent_id)
            winner = board.check_win()
            board.remove(r, c)
            if winner == self.opponent_id:
                return (r, c)
        return random.choice(empty)

    # ── 困难模式：Minimax depth 4 ─────────────────────

    def _choose_hard(
        self,
        board: Board,
        my_moves: list[tuple[int, int]],
        opp_moves: list[tuple[int, int]],
    ) -> tuple[int, int]:
        empty = board.empty_cells()

        if len(empty) >= 7:
            preferred = [(0, 0), (0, 2), (2, 0), (2, 2), (1, 1)]
            candidates = [m for m in preferred if m in empty]
            if candidates:
                return random.choice(candidates)

        best_move = empty[0]
        best_score = -INF
        alpha, beta = -INF, INF

        for r, c in empty:
            new_my = list(my_moves)
            new_my.append((r, c))
            removed: Optional[tuple[int, int]] = None
            if len(new_my) > 3:
                removed = new_my.pop(0)

            board.place(r, c, self.player_id)
            if removed is not None:
                board.remove(removed[0], removed[1])

            score = self._minimax(
                board, new_my, list(opp_moves), depth=4,
                alpha=alpha, beta=beta, is_maximizing=False,
            )

            board.remove(r, c)
            if removed is not None:
                board.place(removed[0], removed[1], self.player_id)

            if score > best_score:
                best_score = score
                best_move = (r, c)
            alpha = max(alpha, score)

        return best_move

    # ── Minimax ───────────────────────────────────────

    def _minimax(
        self,
        board: Board,
        my_moves: list[tuple[int, int]],
        opp_moves: list[tuple[int, int]],
        depth: int,
        alpha: float,
        beta: float,
        is_maximizing: bool,
    ) -> int:
        winner = board.check_win()
        if winner == self.player_id:
            return 100 + depth
        if winner == self.opponent_id:
            return -100 - depth
        if depth == 0:
            return self._evaluate(board, my_moves, opp_moves)

        empty = board.empty_cells()
        if not empty:
            return 0

        if is_maximizing:
            return self._max_node(board, my_moves, opp_moves, empty, depth, alpha, beta)
        else:
            return self._min_node(board, my_moves, opp_moves, empty, depth, alpha, beta)

    def _max_node(self, board, my_moves, opp_moves, empty, depth, alpha, beta):
        best = -INF
        for r, c in empty:
            new_my = list(my_moves)
            new_my.append((r, c))
            removed = new_my.pop(0) if len(new_my) > 3 else None

            board.place(r, c, self.player_id)
            if removed is not None:
                board.remove(removed[0], removed[1])

            score = self._minimax(
                board, new_my, list(opp_moves), depth - 1,
                alpha=alpha, beta=beta, is_maximizing=False,
            )

            board.remove(r, c)
            if removed is not None:
                board.place(removed[0], removed[1], self.player_id)

            best = max(best, score)
            alpha = max(alpha, score)
            if alpha >= beta:
                break
        return best

    def _min_node(self, board, my_moves, opp_moves, empty, depth, alpha, beta):
        best = INF
        for r, c in empty:
            new_opp = list(opp_moves)
            new_opp.append((r, c))
            removed = new_opp.pop(0) if len(new_opp) > 3 else None

            board.place(r, c, self.opponent_id)
            if removed is not None:
                board.remove(removed[0], removed[1])

            score = self._minimax(
                board, list(my_moves), new_opp, depth - 1,
                alpha=alpha, beta=beta, is_maximizing=True,
            )

            board.remove(r, c)
            if removed is not None:
                board.place(removed[0], removed[1], self.opponent_id)

            best = min(best, score)
            beta = min(beta, score)
            if alpha >= beta:
                break
        return best

    def _evaluate(
        self,
        board: Board,
        my_moves: list[tuple[int, int]],
        opp_moves: list[tuple[int, int]],
    ) -> int:
        score = 0
        lines = [
            [(0, 0), (0, 1), (0, 2)], [(1, 0), (1, 1), (1, 2)],
            [(2, 0), (2, 1), (2, 2)], [(0, 0), (1, 0), (2, 0)],
            [(0, 1), (1, 1), (2, 1)], [(0, 2), (1, 2), (2, 2)],
            [(0, 0), (1, 1), (2, 2)], [(0, 2), (1, 1), (2, 0)],
        ]
        my_set = set(my_moves)
        opp_set = set(opp_moves)

        for line in lines:
            my_count = sum(1 for p in line if p in my_set)
            opp_count = sum(1 for p in line if p in opp_set)
            if my_count > 0 and opp_count == 0:
                score += my_count ** 2
            if opp_count > 0 and my_count == 0:
                score -= opp_count ** 2 * 2

        return score
