# 🌙 月亮棋 Moon Chess

原神小游戏的 Python 实现。3×3 棋盘，每方最多 3 枚棋子，落第 4 子时最早棋子自动隐去，率先达成三连者胜。

## 运行

```bash
pip install -r moon_chess/requirements.txt
python -m moon_chess
```

## 游戏模式

| 模式 | 说明 |
|------|------|
| 联机对战 | 通过中继服务器匹配，房间码 4 位字母 |
| 人机·简单 | 贪心 AI（先胜后堵） |
| 人机·困难 | Minimax + Alpha-Beta 剪枝，深度 4 |
| 本地双人 | 同屏热座 PvP |

## 打包

```bash
pip install pyinstaller
pyinstaller --clean --noconfirm moon_chess/MoonChess.spec
# 输出 → dist/MoonChess.exe
```

## 部署中继服务器

```bash
pip install -r moon_chess/requirements-relay.txt
python moon_chess/src/relay_server.py
```

或部署到 Render.com，配置见 [render.yaml](render.yaml)。

## 项目结构

```
moon_chess/
├── src/
│   ├── main.py          # 入口 & 主循环
│   ├── board.py         # 3×3 棋盘模型
│   ├── player.py        # 玩家（FIFO 队列，max 3 子）
│   ├── game.py          # 回合管理与胜负判定
│   ├── ai.py            # AI（简单贪心 / Minimax）
│   ├── ui.py            # Pygame 图形界面
│   ├── network.py       # 联机客户端（WebSocket）
│   └── relay_server.py  # 中继服务器
├── fonts/               # 内嵌字体
├── MoonChess.spec       # PyInstaller 打包配置
└── build_exe.bat        # 一键打包脚本
```
