"""月亮棋联机中继服务器

本机测试：
  pip install websockets
  python relay_server.py

部署到 Render.com（免费）：
  1. 创建 Web Service，指向仓库
  2. Build Command:  pip install websockets
  3. Start Command:  python relay_server.py
  4. Render 自动分配 PORT 环境变量

客户端通过房间码自动匹配，中继转发所有对局消息。
"""

import asyncio
import json
import logging
import os
import random
import string
import time

import websockets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("relay")

PORT = int(os.environ.get("PORT", 721))
HOST = "0.0.0.0"
MAX_MSG_SIZE = 4096        # 限制消息大小，防止滥用
ROOM_TIMEOUT = 600         # 房间超时（秒），10 分钟未满则清理
rooms: dict[str, list] = {}           # code -> [ws1, ws2?]
room_times: dict[str, float] = {}     # code -> 创建时间戳


def _gen_code() -> str:
    return "".join(random.choices(string.ascii_uppercase, k=4))


def _get_partner(room_code: str, player_id: int):
    """安全获取对手 WebSocket。"""
    if room_code not in rooms:
        return None
    entry = rooms[room_code]
    if player_id == 1 and len(entry) == 2:
        return entry[1]
    if player_id == 2:
        return entry[0]
    return None


def _is_valid_move(msg: dict) -> bool:
    """验证移动消息格式。"""
    row = msg.get("row")
    col = msg.get("col")
    return (
        isinstance(row, int) and isinstance(col, int)
        and 0 <= row <= 2 and 0 <= col <= 2
    )


async def handler(ws) -> None:
    room: str | None = None
    player: int = 0
    msg_count: int = 0
    try:
        async for raw in ws:
            msg_count += 1
            # 基础速率限制：单连接最多 200 条消息
            if msg_count > 200:
                await ws.send(json.dumps({"type": "error", "msg": "消息过多，连接关闭"}))
                return

            msg = json.loads(raw)
            t = msg.get("type")

            if t == "create":
                code = None
                for _ in range(20):
                    candidate = _gen_code()
                    if candidate not in rooms:
                        code = candidate
                        break
                if code is None:
                    await ws.send(json.dumps({"type": "error", "msg": "服务器繁忙，请稍后重试"}))
                    logger.warning("房间码生成耗尽")
                    return
                rooms[code] = [ws]
                room_times[code] = time.time()
                room = code
                player = 1
                await ws.send(json.dumps({"type": "created", "room": code}))
                logger.info("房间 %s 已创建", code)

            elif t == "join":
                code = msg.get("room", "").upper()
                if code in rooms and len(rooms[code]) == 1:
                    rooms[code].append(ws)
                    room = code
                    player = 2
                    await rooms[code][0].send(json.dumps({"type": "start", "player": 1}))
                    await ws.send(json.dumps({"type": "start", "player": 2}))
                    logger.info("玩家加入房间 %s", code)
                else:
                    await ws.send(json.dumps({"type": "error", "msg": "房间不存在或已满"}))

            elif t == "move":
                if room is None or room not in rooms:
                    continue
                if not _is_valid_move(msg):
                    await ws.send(json.dumps({"type": "error", "msg": "非法移动格式"}))
                    continue
                partner = _get_partner(room, player)
                if partner is not None:
                    await partner.send(json.dumps(
                        {"type": "move", "row": msg["row"], "col": msg["col"]}))

            elif t in ("rematch", "rematch_accept"):
                if room is None or room not in rooms:
                    continue
                partner = _get_partner(room, player)
                if partner is not None:
                    await partner.send(json.dumps({"type": t}))

    except websockets.ConnectionClosed:
        pass
    finally:
        if room and room in rooms:
            try:
                partner = _get_partner(room, player)
                if partner is not None:
                    await partner.send(json.dumps({"type": "opponent_left"}))
            except Exception:
                logger.debug("通知对手离开失败", exc_info=True)
            rooms.pop(room, None)
            room_times.pop(room, None)
            logger.info("房间 %s 已关闭", room)


async def _cleanup_stale_rooms() -> None:
    """定期清理超时的未满房间。"""
    while True:
        await asyncio.sleep(60)  # 每分钟检查一次
        now = time.time()
        stale = [
            code for code, ts in room_times.items()
            if now - ts > ROOM_TIMEOUT and len(rooms.get(code, [])) == 1
        ]
        for code in stale:
            entry = rooms.pop(code, None)
            room_times.pop(code, None)
            if entry:
                try:
                    await entry[0].send(json.dumps(
                        {"type": "error", "msg": "房间超时，未找到对手"}
                    ))
                    await entry[0].close()
                except Exception:
                    pass
            logger.info("清理过期房间 %s", code)


async def main():
    print(f"中继服务器: {HOST}:{PORT}")
    async with websockets.serve(handler, HOST, PORT, max_size=MAX_MSG_SIZE):
        cleanup = asyncio.create_task(_cleanup_stale_rooms())
        try:
            await asyncio.Future()
        finally:
            cleanup.cancel()

if __name__ == "__main__":
    asyncio.run(main())
