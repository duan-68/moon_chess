"""Pygame GUI：菜单、棋盘渲染、点击交互"""

from __future__ import annotations

import math
import os
from typing import Optional, TYPE_CHECKING

import pygame

from moon_chess.src.board import Board
from moon_chess.src.player import Player
from moon_chess.src.network import get_relay_url, set_relay_url


def _is_valid_relay_url(url: str) -> bool:
    """验证中继服务器地址格式。"""
    return url.startswith(("ws://", "wss://")) and len(url) > 8

if TYPE_CHECKING:
    from moon_chess.src.network import NetworkSession

# ── 窗口常量 ───────────────────────────────────────────

# 窗口尺寸
WINDOW_W = 600
WINDOW_H = 700
FPS = 60

# 棋盘布局
CELL_SIZE = 150          # 单格边长
CELL_GAP = 4             # 格子间距
BOARD_ORIGIN_X = 72      # 棋盘左上角 X
BOARD_ORIGIN_Y = 100     # 棋盘左上角 Y

# 棋子
PIECE_RADIUS = 55        # 棋子半径

# ── 颜色 ───────────────────────────────────────────────

# 背景 & 界面
BG = (18, 18, 40)             # 夜空底色
BAR_BG = (28, 28, 55)         # 顶栏 / 底栏
CELL_BG = (35, 35, 65)        # 空格子
CELL_HOVER = (50, 50, 90)     # 悬停高亮
GRID_LINE = (80, 85, 120)     # 网格线
TEXT_MAIN = (220, 220, 240)   # 主文字
TEXT_DIM = (130, 130, 160)    # 次要文字
WHITE = (255, 255, 255)       # 纯白

# 玩家 1 — 红方（明月）  对角线渐变：左上月白 → 右下胭脂
P1_TL = (240, 218, 210)       # 左上 月白
P1_BR = (168, 25, 45)         # 右下 胭脂
P1_COLOR = P1_BR              # 兼容旧引用（底栏色块等）

# 玩家 2 — 蓝方（暗月）  对角线渐变：左上浅白 → 右下靛蓝
P2_TL = (225, 228, 238)       # 左上 浅白
P2_BR = (45, 25, 155)         # 右下 靛蓝
P2_COLOR = P2_BR              # 兼容旧引用（底栏色块等）

# 最旧棋子标记
OLDEST_RING = (255, 80, 80)   # 内圈红
OLDEST_RING_2 = (255, 130, 130)  # 外圈浅红

# 按钮
BTN_NORMAL = (45, 45, 80)     # 按钮底色
BTN_HOVER = (70, 70, 120)     # 悬停底色
BTN_TEXT = (220, 220, 240)    # 按钮文字

# ── 字体（延迟加载）─────────────────────────────────────

_fonts_cache: Optional[dict[str, pygame.font.Font]] = None


def _resolve_bundled_font(filename: str) -> str:
    """解析字体文件路径，兼容开发环境和 PyInstaller 打包环境。

    PyInstaller 通过 datas 将 moon_chess/fonts/ 复制到 _MEIPASS 下，
    开发环境则从 ui.py 所在目录向上两级定位字体目录。
    """
    import sys as _sys
    if getattr(_sys, "frozen", False):
        return os.path.join(_sys._MEIPASS, "moon_chess", "fonts", filename)
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "fonts", filename,
    )


def _make_fonts() -> dict[str, pygame.font.Font]:
    """创建字体缓存，优先按文件路径加载以避免 PyInstaller 兼容问题。

    加载优先级（从高到低）：
      1. 打包/项目中的 simsun.ttc
      2. 系统目录下已知中文字体文件
      3. pygame 内置默认字体（保底，不含中文）
    """
    _FALLBACK = {
        "small": pygame.font.Font(None, 22),
        "mid": pygame.font.Font(None, 28),
        "big": pygame.font.Font(None, 40),
        "title": pygame.font.Font(None, 52),
        "huge": pygame.font.Font(None, 64),
    }

    # ── 构建候选字体路径 ──────────────────────────────
    candidates: list[str] = []

    # 1) 项目自带字体
    bundled = _resolve_bundled_font("simsun.ttc")
    if os.path.exists(bundled):
        candidates.append(bundled)

    # 2) 系统常见中文字体
    windir = os.environ.get("WINDIR", "C:\\Windows")
    for name in ("simsun.ttc", "msyh.ttc", "msyh.ttf", "simhei.ttf"):
        path = os.path.join(windir, "Fonts", name)
        if os.path.exists(path) and path not in candidates:
            candidates.append(path)

    # ── 按路径加载 ─────────────────────────────────────
    for path in candidates:
        try:
            return {
                "small": pygame.font.Font(path, 18),
                "mid": pygame.font.Font(path, 24),
                "big": pygame.font.Font(path, 36),
                "title": pygame.font.Font(path, 48),
                "huge": pygame.font.Font(path, 60),
            }
        except Exception:
            continue

    return _FALLBACK


def _get_fonts() -> dict[str, pygame.font.Font]:
    """延迟初始化字体（需要 pygame.init() 已调用）。"""
    global _fonts_cache
    if _fonts_cache is None:
        _fonts_cache = _make_fonts()
    return _fonts_cache


# 字体延迟加载：调用 _get_fonts() 获取（首次调用需要 pygame.init() 已完成）

# 渐变表面缓存（避免每帧重建像素）
_gradient_cache: dict[tuple, pygame.Surface] = {}


def _cached_gradient(tl: tuple[int, int, int], br: tuple[int, int, int]) -> pygame.Surface:
    """返回带棱面切割纹理的对角线渐变圆表面，按颜色缓存。"""
    key = (tl, br)
    if key not in _gradient_cache:
        d = PIECE_RADIUS * 2
        cx = cy = PIECE_RADIUS
        surf = pygame.Surface((d, d), pygame.SRCALPHA)
        tl_r, tl_g, tl_b = tl
        br_r, br_g, br_b = br

        # ── 像素级对角线渐变圆 ──────────────────────
        for py in range(d):
            for px in range(d):
                dx = px - cx
                dy = py - cy
                if dx * dx + dy * dy > PIECE_RADIUS * PIECE_RADIUS:
                    continue
                t = (px + py) / (2 * (d - 1)) if d > 1 else 0
                r = int(tl_r + (br_r - tl_r) * t)
                g = int(tl_g + (br_g - tl_g) * t)
                b = int(tl_b + (br_b - tl_b) * t)
                surf.set_at((px, py), (r, g, b, 255))

        # ── 棱面切割纹理 ────────────────────────────
        _add_facets(surf, cx, cy)

        _gradient_cache[key] = surf
    return _gradient_cache[key].copy()


def _add_facets(surf: pygame.Surface, cx: int, cy: int) -> None:
    """在渐变圆上叠加宝石棱面切割纹理。

    标准明亮式切割 (brilliant cut) 俯视结构：
      中心六边形台面 → 六枚主冠面（风筝形）→ 十二枚上腰面
    """
    R = PIECE_RADIUS
    overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)

    # ── 台面（中心六边形） ──────────────────────────
    TABLE_R = R * 0.30  # 台面半径
    table: list[tuple[float, float]] = []
    for i in range(6):
        a = 2 * math.pi * i / 6 - math.pi / 2
        table.append((cx + TABLE_R * math.cos(a), cy + TABLE_R * math.sin(a)))

    # ── 主冠面 6 枚（台面边 → 外缘） ──────────────
    # 台面每条边的中点
    edge_mids: list[tuple[float, float]] = []
    for i in range(6):
        p1 = table[i]
        p2 = table[(i + 1) % 6]
        edge_mids.append(((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2))

    # 外缘对应点（台面顶点方向偏移一些角度）
    girdle_pts: list[tuple[float, float]] = []
    for i in range(6):
        a = 2 * math.pi * i / 6 - math.pi / 2
        girdle_pts.append((cx + R * math.cos(a), cy + R * math.sin(a)))
    # 外缘腰点（台面边中点方向）
    girdle_mids: list[tuple[float, float]] = []
    for i in range(6):
        a = 2 * math.pi * (i + 0.5) / 6 - math.pi / 2
        girdle_mids.append((cx + R * math.cos(a), cy + R * math.sin(a)))

    # ── 绘制各棱面 ────────────────────────────────
    # 6 枚主冠面（风筝形）：table_edge_mid → table两个顶点 → girdle_mid
    for i in range(6):
        pts = [
            edge_mids[i],
            table[(i + 1) % 6],
            girdle_mids[i],
            table[i],
        ]
        # 根据角度决定明暗（模拟单一光源从左上）
        angle = 2 * math.pi * (i + 0.5) / 6
        brightness = 35 + int(25 * math.cos(angle + math.pi / 4))
        alpha = max(10, min(60, brightness))
        pygame.draw.polygon(overlay, (255, 255, 255, alpha), pts)

    # 6 枚星面（上腰面 A）：table_vertex → girdle_mid → girdle_vertex
    for i in range(6):
        pts = [
            table[i],
            girdle_mids[(i - 1) % 6],
            girdle_pts[i],
            girdle_mids[i],
        ]
        angle = 2 * math.pi * i / 6
        brightness = 25 + int(30 * math.cos(angle + math.pi / 3))
        alpha = max(5, min(55, brightness))
        pygame.draw.polygon(overlay, (0, 0, 0, alpha), pts)

    # ── 台面略微提亮 ──────────────────────────────
    pygame.draw.polygon(overlay, (255, 255, 255, 30), table)

    # ── 棱线（白色细线勾勒切割边界） ──────────────
    line_c = (255, 255, 255, 55)
    # 台面边
    for i in range(6):
        pygame.draw.line(overlay, line_c, table[i], table[(i + 1) % 6], width=1)
    # 顶点 → 外缘
    for i in range(6):
        pygame.draw.line(overlay, line_c, table[i], girdle_pts[i], width=1)
    # 边中点 → 外缘中点
    for i in range(6):
        pygame.draw.line(overlay, line_c, edge_mids[i], girdle_mids[i], width=1)
    # 外缘腰点之间的连线
    all_girdle = []
    for i in range(6):
        all_girdle.append(girdle_pts[i])
        all_girdle.append(girdle_mids[i])
    for i in range(12):
        pygame.draw.line(overlay, line_c, all_girdle[i], all_girdle[(i + 1) % 12], width=1)

    surf.blit(overlay, (0, 0))

# ── 工具函数 ────────────────────────────────────────────


def cell_rect(row: int, col: int) -> pygame.Rect:
    """返回棋盘格子的矩形区域。"""
    x = BOARD_ORIGIN_X + col * (CELL_SIZE + CELL_GAP)
    y = BOARD_ORIGIN_Y + row * (CELL_SIZE + CELL_GAP)
    return pygame.Rect(x, y, CELL_SIZE, CELL_SIZE)


def cell_at_pos(mx: int, my: int) -> Optional[tuple[int, int]]:
    """像素坐标 -> (row, col)，不在格子上返回 None。"""
    for r in range(3):
        for c in range(3):
            if cell_rect(r, c).collidepoint(mx, my):
                return (r, c)
    return None


def _get_order(player: Player, row: int, col: int) -> int:
    """获取棋子在玩家队列中的序号（1-based），0=未找到。"""
    for i, (r, c) in enumerate(player.moves):
        if r == row and c == col:
            return i + 1
    return 0


def _is_oldest(player: Player, row: int, col: int) -> bool:
    """该棋子是否为玩家最旧（即将被淘汰）的棋子。"""
    if player.piece_count <= 1:
        return False
    return player.moves[0] == (row, col)


def _format_moves(p: Player) -> str:
    """棋子列表 -> 'A1, B2, C3' 格式。"""
    if not p.moves:
        return "(无)"
    return ", ".join(f"{chr(ord('A') + r)}{c + 1}" for r, c in p.moves)


# ── 按钮组件 ────────────────────────────────────────────


class Button:
    """可点击的圆角按钮。"""

    def __init__(self, x: int, y: int, w: int, h: int, text: str) -> None:
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self._hover = False

    def update(self, mx: int, my: int) -> None:
        self._hover = self.rect.collidepoint(mx, my)

    def draw(self, screen: pygame.Surface) -> None:
        color = BTN_HOVER if self._hover else BTN_NORMAL
        r = 12
        pygame.draw.rect(screen, color, self.rect, border_radius=r)
        pygame.draw.rect(screen, GRID_LINE, self.rect, width=2, border_radius=r)
        label = _get_fonts()["big"].render(self.text, True, BTN_TEXT)
        screen.blit(label, label.get_rect(center=self.rect.center))

    def clicked(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)


# ── 绘制函数 ────────────────────────────────────────────


def _text_center(
    screen: pygame.Surface, text: str, font_key: str, color: tuple, y: int
) -> None:
    surf = _get_fonts()[font_key].render(text, True, color)
    screen.blit(surf, surf.get_rect(center=(WINDOW_W // 2, y)))


def _text_left(
    screen: pygame.Surface, text: str, font_key: str, color: tuple, x: int, y: int
) -> None:
    surf = _get_fonts()[font_key].render(text, True, color)
    screen.blit(surf, (x, y))


def _dashed_ring(
    screen: pygame.Surface, cx: int, cy: int, radius: int,
    color: tuple, offset: float = 0.0, alpha: int = 255,
) -> None:
    """绘制虚线圆环，支持透明度（用于脉冲动画）。"""
    seg_size = (radius + 5) * 2
    temp = pygame.Surface((seg_size, seg_size), pygame.SRCALPHA)
    tcx, tcy = seg_size // 2, seg_size // 2
    rgba = (*color, alpha)

    segments = 16
    for i in range(segments):
        if i % 2 != 0:
            continue
        a0 = offset + 2 * math.pi * i / segments
        a1 = offset + 2 * math.pi * (i + 0.7) / segments
        pts = [
            (
                tcx + radius * math.cos(a0 + (a1 - a0) * t / 8),
                tcy + radius * math.sin(a0 + (a1 - a0) * t / 8),
            )
            for t in range(9)
        ]
        if len(pts) >= 2:
            pygame.draw.lines(temp, rgba, False, pts, width=2)

    screen.blit(temp, (cx - tcx, cy - tcy))


def draw_piece(
    screen: pygame.Surface, cx: int, cy: int,
    player_id: int, is_oldest: bool,
) -> None:
    """绘制一枚对角线渐变棋子。

    最旧棋子会整体时隐时现（脉冲透明度动画）。
    """
    tl, br = (P1_TL, P1_BR) if player_id == 1 else (P2_TL, P2_BR)

    # 渲染到临时表面（统一处理脉冲 & 渐变）
    pad = 6  # 阴影偏移留白
    size = (PIECE_RADIUS + pad) * 2
    temp = pygame.Surface((size, size), pygame.SRCALPHA)
    tcx, tcy = size // 2, size // 2

    _draw_piece_body(temp, tcx, tcy, tl, br)

    if is_oldest:
        pulse = (math.sin(pygame.time.get_ticks() * 0.005) + 1) / 2
        alpha = int(55 + pulse * 200)
        temp.set_alpha(alpha)

    screen.blit(temp, (cx - tcx, cy - tcy))


def _draw_piece_body(
    screen: pygame.Surface, cx: int, cy: int,
    tl: tuple[int, int, int],
    br: tuple[int, int, int],
) -> None:
    """绘制棋子本体：对角线渐变圆 + 阴影 + 边框。"""

    # 阴影（圆形，偏右下）
    pygame.draw.circle(screen, (0, 0, 0, 80), (cx + 4, cy + 4), PIECE_RADIUS)

    # 对角线渐变主体（缓存）
    grad = _cached_gradient(tl, br)
    screen.blit(grad, (cx - PIECE_RADIUS, cy - PIECE_RADIUS))

    # 边框
    br_r, br_g, br_b = br
    border_c = (br_r // 2, br_g // 2, br_b // 2)
    pygame.draw.circle(screen, border_c, (cx, cy), PIECE_RADIUS, width=3)


def draw_board(
    screen: pygame.Surface,
    board: Board,
    players: tuple[Player, Player],
    hover_pos: Optional[tuple[int, int]],
) -> None:
    """绘制棋盘及所有棋子。"""
    # 列标 1 2 3
    for c in range(3):
        x = BOARD_ORIGIN_X + c * (CELL_SIZE + CELL_GAP) + CELL_SIZE // 2
        s = _get_fonts()["mid"].render(str(c + 1), True, TEXT_DIM)
        screen.blit(s, s.get_rect(center=(x, BOARD_ORIGIN_Y - 28)))

    for r in range(3):
        # 行标 A B C
        s = _get_fonts()["mid"].render(chr(ord("A") + r), True, TEXT_DIM)
        screen.blit(s, s.get_rect(center=(
            BOARD_ORIGIN_X - 28,
            BOARD_ORIGIN_Y + r * (CELL_SIZE + CELL_GAP) + CELL_SIZE // 2,
        )))

        for c in range(3):
            rect = cell_rect(r, c)
            val = board.cell(r, c)

            # 格子背景
            is_hover = hover_pos == (r, c) and val is None
            bg = CELL_HOVER if is_hover else CELL_BG
            pygame.draw.rect(screen, bg, rect, border_radius=8)

            if val is not None:
                player = players[val - 1]
                oldest = _is_oldest(player, r, c)
                draw_piece(screen, rect.centerx, rect.centery, val, oldest)
            elif is_hover:
                # 半透明预览圈
                srf = pygame.Surface((PIECE_RADIUS * 2, PIECE_RADIUS * 2), pygame.SRCALPHA)
                pygame.draw.circle(srf, (*CELL_HOVER, 80), (PIECE_RADIUS, PIECE_RADIUS), PIECE_RADIUS)
                screen.blit(srf, (rect.centerx - PIECE_RADIUS, rect.centery - PIECE_RADIUS))


def draw_top_bar(screen: pygame.Surface, mode_label: str, step: int, in_game: bool) -> None:
    """顶部信息栏。"""
    pygame.draw.rect(screen, BAR_BG, (0, 0, WINDOW_W, 65))
    pygame.draw.line(screen, GRID_LINE, (0, 65), (WINDOW_W, 65))

    if in_game:
        _text_left(screen, "< 返回 (ESC)", "small", TEXT_DIM, 15, 20)

    title = _get_fonts()["mid"].render(f"月亮棋  {mode_label}", True, TEXT_MAIN)
    screen.blit(title, title.get_rect(center=(WINDOW_W // 2, 32)))

    step_s = _get_fonts()["small"].render(f"第 {step} 步", True, TEXT_DIM)
    screen.blit(step_s, step_s.get_rect(midright=(WINDOW_W - 20, 32)))


def draw_bottom_bar(
    screen: pygame.Surface,
    players: tuple[Player, Player],
    current_player: Player,
) -> None:
    """底部棋子状态栏。"""
    bar_top = 580
    pygame.draw.rect(screen, BAR_BG, (0, bar_top, WINDOW_W, WINDOW_H - bar_top))
    pygame.draw.line(screen, GRID_LINE, (0, bar_top), (WINDOW_W, bar_top))

    py = bar_top + 14
    for p in players:
        marker_c = P1_COLOR if p.id == 1 else P2_COLOR
        marker = "(A)" if p.id == 1 else "(B)"
        arrow = "  <<<" if p.id == current_player.id else ""

        # 颜色方块
        box = pygame.Surface((14, 14))
        box.fill(marker_c)
        screen.blit(box, (20, py + 4))

        _text_left(screen, f"{marker} {p.name}: {_format_moves(p)}{arrow}", "small", TEXT_MAIN, 42, py)
        py += 26

        # 最旧棋子淘汰提示
        if p.piece_count == 3:
            r, c = p.moves[0]
            label = f"{chr(ord('A') + r)}{c + 1}"
            _text_left(screen, f"    [{label} 最旧 -> 下次落子将隐去]", "small", OLDEST_RING, 42, py)
            py += 24

        py += 6


def draw_result_overlay(
    screen: pygame.Surface, winner: Optional[Player], btn: Button,
) -> None:
    """结果画面遮罩。"""
    overlay = pygame.Surface((WINDOW_W, WINDOW_H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    pw, ph = 380, 200
    px = (WINDOW_W - pw) // 2
    py = (WINDOW_H - ph) // 2 - 30
    panel = pygame.Rect(px, py, pw, ph)
    pygame.draw.rect(screen, BAR_BG, panel, border_radius=16)
    pygame.draw.rect(screen, GRID_LINE, panel, width=2, border_radius=16)

    if winner is not None:
        c = P1_COLOR if winner.id == 1 else P2_COLOR
        _text_center(screen, f"{winner.name} 获胜！", "title", c, py + 40)
        _text_center(screen, "三连达成", "big", TEXT_MAIN, py + 85)
    else:
        _text_center(screen, "平局", "title", TEXT_MAIN, py + 60)

    btn.draw(screen)
    _text_center(screen, "点击按钮返回菜单", "small", TEXT_DIM, WINDOW_H - 20)


# ── 主 UI 类 ────────────────────────────────────────────


AI_DELAY_MS = 350  # AI 落子前思考延时


class MoonChessUI:
    """Pygame 月亮棋主界面。"""

    def __init__(self) -> None:
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        pygame.display.set_caption("月亮棋  Moon Chess")
        self.clock = pygame.time.Clock()
        self._running = True

    # ── 菜单 ──────────────────────────────────────────

    def show_menu(self) -> str:
        """显示主菜单，返回模式字符串。"""
        btn_w, btn_h = 260, 56
        btn_cx = WINDOW_W // 2 - btn_w // 2
        buttons = [
            Button(btn_cx, 260, btn_w, btn_h, "联机对战  在线"),
            Button(btn_cx, 340, btn_w, btn_h, "人机对战  简单"),
            Button(btn_cx, 420, btn_w, btn_h, "人机对战  困难"),
            Button(btn_cx, 500, btn_w, btn_h, "退    出"),
        ]
        modes = ["online", "simple", "hard", "quit"]

        while self._running:
            mx, my = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for btn, mode in zip(buttons, modes):
                        if btn.clicked(event.pos):
                            return mode

            for btn in buttons:
                btn.update(mx, my)

            self.screen.fill(BG)
            _text_center(self.screen, "月 亮 棋", "title", TEXT_MAIN, 110)
            _text_center(self.screen, "Moon Chess", "big", TEXT_DIM, 160)
            _text_center(self.screen, "原神小游戏", "small", TEXT_DIM, 200)

            for btn in buttons:
                btn.draw(self.screen)

            pygame.display.flip()
            self.clock.tick(FPS)

        return "quit"

    # ── 对局循环 ──────────────────────────────────────

    def run_game(self, game, ai) -> None:
        """运行一局游戏。game=Game 实例，ai=MoonChessAI 或 None。"""
        mode_label = "PvP"
        if ai is not None:
            mode_label = "AI 简单" if ai.difficulty == "simple" else "AI 困难"

        result_shown = False
        result_btn = Button(
            WINDOW_W // 2 - 130, WINDOW_H // 2 + 100, 260, 50, "返回菜单"
        )
        ai_scheduled_time: int = 0
        ai_pending: bool = False

        while self._running:
            mx, my = pygame.mouse.get_pos()
            now = pygame.time.get_ticks()

            # ── 事件处理 ─────────────────────────────
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._running = False
                    return

                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return  # 返回菜单

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    # 顶栏返回
                    if my < 65:
                        return

                    if result_shown:
                        if result_btn.clicked(event.pos):
                            return
                        continue

                    # 落子
                    if self._is_human_turn(game, ai):
                        pos = cell_at_pos(mx, my)
                        if pos is not None and game.is_legal_move(*pos):
                            game.make_move(*pos)
                            if not game.is_over and ai is not None:
                                ai_scheduled_time = now + AI_DELAY_MS
                                ai_pending = True

            # ── AI 延时落子 ───────────────────────────
            if ai_pending and not game.is_over and now >= ai_scheduled_time:
                ai_pending = False
                if self._is_ai_turn(game, ai):
                    row, col = ai.choose_move(
                        game.board,
                        game.players[ai.player_id - 1].moves,
                        game.players[2 - ai.player_id].moves,
                    )
                    if game.is_legal_move(row, col):
                        game.make_move(row, col)

            # ── 检查游戏结束 ──────────────────────────
            if game.is_over and not result_shown:
                result_shown = True
                result_btn = Button(
                    WINDOW_W // 2 - 130, WINDOW_H // 2 + 100, 260, 50, "返回菜单"
                )

            # ── 渲染 ──────────────────────────────────
            self.screen.fill(BG)

            hover_cell: Optional[tuple[int, int]] = None
            if not result_shown and self._is_human_turn(game, ai):
                hover_cell = cell_at_pos(mx, my)

            draw_top_bar(self.screen, mode_label, game.move_count + 1, in_game=True)
            draw_board(self.screen, game.board, game.players, hover_cell)
            draw_bottom_bar(self.screen, game.players, game.current_player)

            # AI 思考提示
            if ai_pending and not game.is_over:
                _text_center(self.screen, "[AI] 思考中...", "mid", TEXT_DIM, 570)

            if result_shown:
                result_btn.update(mx, my)
                winner = game.players[game.winner - 1] if game.winner else None
                draw_result_overlay(self.screen, winner, result_btn)

            pygame.display.flip()
            self.clock.tick(FPS)

    # ── 辅助 ─────────────────────────────────────────

    @staticmethod
    def _is_human_turn(game, ai) -> bool:
        if ai is None:
            return True
        return game.current_player.id != ai.player_id

    @staticmethod
    def _is_ai_turn(game, ai) -> bool:
        if ai is None:
            return False
        return game.current_player.id == ai.player_id

    # ── 联机流程 ──────────────────────────────────────

    def show_online_lobby(self, net: NetworkSession) -> bool:
        """联机大厅：选择创建或加入房间。返回 True=已匹配, False=取消。"""
        btn_w, btn_h = 280, 56
        btn_cx = WINDOW_W // 2 - btn_w // 2
        btn_create = Button(btn_cx, 320, btn_w, btn_h, "创建房间")
        btn_join = Button(btn_cx, 400, btn_w, btn_h, "加入房间")
        btn_back = Button(btn_cx, 480, btn_w, btn_h, "返    回")

        # 服务器地址显示区（点击可修改）
        server_rect = pygame.Rect(WINDOW_W // 2 - 200, 540, 400, 36)
        editing_server = False
        server_input = ""
        server_hint = ""

        choice = None
        while self._running and choice is None:
            mx, my = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT: return False
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if editing_server:
                        editing_server = False
                        if server_input.strip():
                            set_relay_url(server_input.strip())
                            server_hint = "地址已保存"
                        else:
                            server_hint = ""
                    elif server_rect.collidepoint(event.pos):
                        editing_server = True
                        server_input = get_relay_url()
                    elif btn_create.clicked(event.pos): choice = "create"
                    elif btn_join.clicked(event.pos): choice = "join"
                    elif btn_back.clicked(event.pos): return False
                if event.type == pygame.KEYDOWN and editing_server:
                    if event.key == pygame.K_RETURN:
                        editing_server = False
                        url = server_input.strip()
                        if url:
                            if _is_valid_relay_url(url):
                                set_relay_url(url)
                                server_hint = "地址已保存"
                            else:
                                server_hint = "格式错误，需以 ws:// 或 wss:// 开头"
                        else:
                            server_hint = ""
                    elif event.key == pygame.K_BACKSPACE:
                        server_input = server_input[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        editing_server = False
                        server_hint = ""
                    else:
                        if len(server_input) < 60:
                            server_input += event.unicode
            btn_create.update(mx, my); btn_join.update(mx, my); btn_back.update(mx, my)
            self.screen.fill(BG)
            _text_center(self.screen, "联 机 对 战", "title", TEXT_MAIN, 150)
            _text_center(self.screen, "通过房间码匹配对手", "small", TEXT_DIM, 220)
            btn_create.draw(self.screen); btn_join.draw(self.screen); btn_back.draw(self.screen)

            # ── 服务器设置区域 ──────────────────────────
            _text_center(self.screen, "中继服务器 ", "small", TEXT_DIM, 600)
            if editing_server:
                c = P1_COLOR
                display = server_input if server_input else "_"
            else:
                c = CELL_HOVER if server_rect.collidepoint(mx, my) else CELL_BG
                display = get_relay_url()
            pygame.draw.rect(self.screen, c, server_rect, border_radius=8)
            txt_surf = _get_fonts()["small"].render(display, True, TEXT_MAIN if editing_server else TEXT_DIM)
            self.screen.blit(txt_surf, txt_surf.get_rect(center=server_rect.center))
            if server_hint:
                _text_center(self.screen, server_hint, "small", P1_COLOR, 590)

            pygame.display.flip(); self.clock.tick(FPS)

        if choice == "create": return self._host_room(net)
        elif choice == "join": return self._join_room(net)
        return False

    def _host_room(self, net: NetworkSession) -> bool:
        net.create_room()
        while self._running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: net.close(); return False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    net.close(); return False
            if net.error:
                # 显示错误 2 秒后返回
                for _ in range(120):
                    self.screen.fill(BG)
                    _text_center(self.screen, "连接失败", "title", OLDEST_RING, 200)
                    _text_center(self.screen, net.error, "mid", TEXT_MAIN, 280)
                    _text_center(self.screen, "即将返回菜单...", "small", TEXT_DIM, 380)
                    pygame.display.flip(); self.clock.tick(FPS)
                return False
            if net.room_code and net.started: return True
            self.screen.fill(BG)
            _text_center(self.screen, "等待对手加入...", "big", TEXT_MAIN, 140)
            if net.room_code:
                # ── 大号房间码面板 ──────────────────────
                panel_w, panel_h = 280, 120
                panel_rect = pygame.Rect(
                    WINDOW_W // 2 - panel_w // 2, 200, panel_w, panel_h
                )
                pygame.draw.rect(self.screen, BAR_BG, panel_rect, border_radius=16)
                pygame.draw.rect(self.screen, P1_COLOR, panel_rect, width=3, border_radius=16)
                _text_center(self.screen, "房间码", "mid", TEXT_DIM, 215)
                _text_center(self.screen, net.room_code, "huge", P1_COLOR, 255)
                _text_center(self.screen, "告诉对手这 4 个字母即可加入", "small", TEXT_DIM, 350)
            else:
                _text_center(self.screen, "正在连接中继服务器...", "small", TEXT_DIM, 280)
            _text_center(self.screen, "按 ESC 取消", "small", TEXT_DIM, 480)
            pygame.display.flip(); self.clock.tick(FPS)
        return False

    def _join_room(self, net: NetworkSession) -> bool:
        code = ""; status = ""; joining = False

        # ── 屏幕字母键盘按钮 ──────────────────────────
        LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        key_btns: list[Button] = []
        cols = 13
        btn_size = 36
        gap = 4
        start_x = (WINDOW_W - cols * (btn_size + gap)) // 2
        start_y = 320
        for i, ch in enumerate(LETTERS):
            r, c = divmod(i, cols)
            key_btns.append(Button(
                start_x + c * (btn_size + gap),
                start_y + r * (btn_size + gap),
                btn_size, btn_size, ch,
            ))
        btn_del = Button(start_x, start_y + 2 * (btn_size + gap) + 8, 120, 40, "删除")
        btn_ok = Button(start_x + 130, start_y + 2 * (btn_size + gap) + 8, 120, 40, "确认")
        btn_back = Button(WINDOW_W // 2 - 100, start_y + 2 * (btn_size + gap) + 58, 200, 40, "返回")

        while self._running:
            mx, my = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT: return False
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if joining: net.close(); return False
                    return False
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if not joining:
                        for btn in key_btns:
                            if btn.clicked(event.pos) and len(code) < 4:
                                code += btn.text
                        if btn_del.clicked(event.pos):
                            code = code[:-1]
                        if btn_ok.clicked(event.pos) and len(code) == 4:
                            net.join_room(code); joining = True; status = "加入中..."
                        if btn_back.clicked(event.pos):
                            return False
            if joining and net.error: status = net.error; joining = False
            if joining and net.started: return True

            # ── 渲染 ──────────────────────────────────
            self.screen.fill(BG)
            _text_center(self.screen, "加入房间", "big", TEXT_MAIN, 100)
            _text_center(self.screen, "点击字母输入对手的房间码", "small", TEXT_DIM, 150)

            # 房间码显示
            box_w, box_h = 220, 48
            box_rect = pygame.Rect(WINDOW_W // 2 - box_w // 2, 180, box_w, box_h)
            pygame.draw.rect(self.screen, BAR_BG, box_rect, border_radius=10)
            pygame.draw.rect(self.screen, P1_COLOR, box_rect, width=2, border_radius=10)
            display = code.ljust(4, "_")
            txt = _get_fonts()["title"].render(display, True, TEXT_MAIN)
            self.screen.blit(txt, txt.get_rect(center=box_rect.center))

            # 字母按钮
            for btn in key_btns:
                btn.update(mx, my)
                btn.draw(self.screen)

            if not joining:
                btn_del.update(mx, my); btn_del.draw(self.screen)
                btn_ok.update(mx, my); btn_ok.draw(self.screen)
            btn_back.update(mx, my); btn_back.draw(self.screen)

            if status:
                sc = CELL_HOVER if "加入" in status else OLDEST_RING
                _text_center(self.screen, status, "small", sc, 580)

            _text_center(self.screen, "ESC 返回", "small", TEXT_DIM, 630)
            pygame.display.flip(); self.clock.tick(FPS)
        return False

    # ── 联机对局循环 ──────────────────────────────────

    def run_online_game(self, game, net: NetworkSession) -> None:
        """运行联机对局。player_id 由中继分配：1=明月, 2=暗月。

        支持重赛：任一方点击"再来一局"后等待对方确认，双方都同意即重置。
        """
        my_id = net.player_id
        mode_label = "联机 (明月)" if my_id == 1 else "联机 (暗月)"
        result_shown = False
        result_btn = Button(WINDOW_W // 2 - 130, WINDOW_H // 2 + 100, 260, 50, "返回菜单")
        rematch_btn = Button(WINDOW_W // 2 - 130, WINDOW_H // 2 + 160, 260, 50, "再来一局")
        opp_disconnected = False
        i_requested_rematch = False   # 我发起了重赛
        opp_wants_rematch = False     # 对手发起了重赛
        rematch_agreed = False        # 双方都同意

        while self._running:
            mx, my = pygame.mouse.get_pos()
            my_turn = game.current_player.id == my_id

            # ── 网络消息 ─────────────────────────────
            msg = net.recv()
            if msg:
                t = msg.get("type")
                if t == "move" and not my_turn and not result_shown and not opp_disconnected:
                    r = msg.get("row")
                    c = msg.get("col")
                    if isinstance(r, int) and isinstance(c, int) and game.is_legal_move(r, c):
                        game.make_move(r, c)
                elif t == "rematch":
                    if result_shown:
                        opp_wants_rematch = True
                        if i_requested_rematch:
                            rematch_agreed = True
                elif t == "rematch_accept":
                    if i_requested_rematch:
                        rematch_agreed = True
                elif t == "opponent_left":
                    opp_disconnected = True

            # ── 事件 ─────────────────────────────────
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    net.close(); return
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    net.close(); return
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if my < 65:  # 顶栏返回
                        net.close(); return
                    if result_shown:
                        if result_btn.clicked(event.pos):
                            net.close(); return
                        if rematch_btn.clicked(event.pos) and not i_requested_rematch:
                            net.send({"type": "rematch"})
                            i_requested_rematch = True
                            if opp_wants_rematch:
                                rematch_agreed = True
                        continue
                    # 自己的回合才能落子
                    if my_turn and not opp_disconnected:
                        pos = cell_at_pos(mx, my)
                        if pos is not None and game.is_legal_move(*pos):
                            game.make_move(*pos)
                            net.send({"type": "move", "row": pos[0], "col": pos[1]})

            # ── 重赛达成 ─────────────────────────────
            if rematch_agreed:
                net.send({"type": "rematch_accept"})
                game.reset()
                result_shown = False
                i_requested_rematch = False
                opp_wants_rematch = False
                rematch_agreed = False
                opp_disconnected = False
                continue

            # ── 断连检测 ─────────────────────────────
            if not net.connected and not result_shown:
                opp_disconnected = True

            # ── 结果 ─────────────────────────────────
            if game.is_over and not result_shown:
                result_shown = True

            # ── 渲染 ─────────────────────────────────
            self.screen.fill(BG)
            hover_cell = cell_at_pos(mx, my) if (my_turn and not result_shown and not opp_disconnected) else None
            draw_top_bar(self.screen, mode_label, game.move_count + 1, in_game=True)
            draw_board(self.screen, game.board, game.players, hover_cell)
            draw_bottom_bar(self.screen, game.players, game.current_player)

            if opp_disconnected:
                _text_center(self.screen, "对手已断开连接", "big", OLDEST_RING, 570)
            elif not my_turn and not result_shown:
                _text_center(self.screen, "等待对手落子...", "mid", TEXT_DIM, 570)
            else:
                _text_center(self.screen, "你的回合", "mid", P1_COLOR, 570)

            if result_shown:
                result_btn.update(mx, my)
                rematch_btn.update(mx, my)
                winner = game.players[game.winner - 1] if game.winner else None
                draw_result_overlay(self.screen, winner, result_btn)
                # 重赛按钮和状态
                rematch_btn.draw(self.screen)
                if i_requested_rematch and not opp_wants_rematch:
                    _text_center(self.screen, "等待对手回应...", "mid", TEXT_DIM, WINDOW_H // 2 + 220)
                elif opp_wants_rematch and not i_requested_rematch:
                    _text_center(self.screen, "对手想再来一局！请点击再来一局接受", "small", P1_COLOR, WINDOW_H // 2 + 220)

            pygame.display.flip()
            self.clock.tick(FPS)
