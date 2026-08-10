"""入口模块：Pygame 主循环"""

from __future__ import annotations

import sys
import io
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

if sys.platform == "win32" and sys.stdout is not None and sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from moon_chess.src.game import Game
from moon_chess.src.ai import MoonChessAI
from moon_chess.src.ui import MoonChessUI
from moon_chess.src.network import NetworkSession


def main() -> None:
    ui = MoonChessUI()
    while True:
        mode = ui.show_menu()
        if mode == "quit":
            break
        elif mode == "online":
            _run_online(ui)
        else:
            game, ai = _setup_game(mode)
            ui.run_game(game, ai)


def _setup_game(mode: str) -> tuple[Game, MoonChessAI | None]:
    if mode == "simple":
        ai = MoonChessAI(player_id=2, difficulty="simple")
        return Game("你", "[AI]简单"), ai
    elif mode == "hard":
        ai = MoonChessAI(player_id=2, difficulty="hard")
        return Game("你", "[AI]困难"), ai
    return Game("明月", "暗月"), None


def _run_online(ui: MoonChessUI) -> None:
    """联机对战：双方通过中继匹配。"""
    net = NetworkSession()
    if not ui.show_online_lobby(net):
        net.close()
        return

    game = Game("明月 (你)" if net.player_id == 1 else "明月 (对手)",
                "暗月 (你)" if net.player_id == 2 else "暗月 (对手)")
    ui.run_online_game(game, net)


if __name__ == "__main__":
    main()
