"""联机对战：连接中继服务器

双方连接同一中继服务器，通过房间码自动匹配。
中继转发所有对局消息，无需公网 IP 或端口转发。

部署中继服务器：
  python relay_server.py   # 本机测试
  或部署到 Render.com      # 公网使用

客户端配置（优先级从高到低）：
  1. 调用 set_relay_url() 运行时设置
  2. 环境变量 MOON_CHESS_RELAY
  3. 默认值 ws://127.0.0.1:0721
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import queue
import threading
import time
from typing import Optional

import websockets

logger = logging.getLogger(__name__)

# ── 中继服务器地址 ──
DEFAULT_RELAY_URL = "wss://moon-chess-relay.onrender.com"

# ── 网络参数 ──
CONNECT_TIMEOUT = 30.0       # 连接超时（秒），给 Render 冷启动留时间
MATCH_TIMEOUT = 120.0        # 匹配对手超时（秒）
HEARTBEAT_INTERVAL = 20.0    # 心跳间隔（秒）
HEARTBEAT_TIMEOUT = 10.0     # 心跳响应超时（秒）
RECONNECT_RETRIES = 3        # 最大重连次数

_current_relay_url: Optional[str] = None


def get_relay_url() -> str:
    """获取当前中继服务器地址。"""
    if _current_relay_url is not None:
        return _current_relay_url
    return os.environ.get("MOON_CHESS_RELAY", DEFAULT_RELAY_URL)


def set_relay_url(url: str) -> None:
    """运行时设置中继服务器地址（优先级最高）。"""
    global _current_relay_url
    _current_relay_url = url


class NetworkSession:
    """联机会话，通过中继服务器通信。"""

    def __init__(self) -> None:
        self._inbox: queue.Queue[dict] = queue.Queue()
        self._outbox: queue.Queue[dict] = queue.Queue()
        self._connected = threading.Event()
        self._started = threading.Event()
        self._error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._room_code: str = ""
        self._player_id: int = 0   # 1=先手(明月), 2=后手(暗月)

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    @property
    def started(self) -> bool:
        return self._started.is_set()

    @property
    def error(self) -> Optional[str]:
        return self._error

    @property
    def room_code(self) -> str:
        return self._room_code

    @property
    def player_id(self) -> int:
        return self._player_id

    def send(self, msg: dict) -> None:
        self._outbox.put(msg)

    def recv(self) -> Optional[dict]:
        try:
            return self._inbox.get_nowait()
        except queue.Empty:
            return None

    def close(self) -> None:
        self._connected.clear()
        self._outbox.put({"type": "__close__"})
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def create_room(self, relay_url: Optional[str] = None) -> None:
        url = relay_url if relay_url is not None else get_relay_url()
        self._thread = threading.Thread(
            target=_run_async, args=(_client_loop(self, url, create=True),),
            daemon=True,
        )
        self._thread.start()

    def join_room(self, room_code: str, relay_url: Optional[str] = None) -> None:
        url = relay_url if relay_url is not None else get_relay_url()
        self._room_code = room_code.upper()
        self._thread = threading.Thread(
            target=_run_async,
            args=(_client_loop(self, url, create=False),),
            daemon=True,
        )
        self._thread.start()


# ══════════════════════════════════════════════════

def _run_async(coro) -> None:
    asyncio.run(coro)


async def _poll_event(session: NetworkSession, interval: float = 0.1) -> None:
    """异步轮询，_started 被设置或连接断开时返回。"""
    while not session._started.is_set() and session._connected.is_set():
        await asyncio.sleep(interval)
    if not session._connected.is_set():
        return


async def _client_loop(session: NetworkSession, url: str, create: bool) -> None:
    try:
        # 连接超时
        ws = await asyncio.wait_for(
            websockets.connect(url), timeout=CONNECT_TIMEOUT
        )
    except asyncio.TimeoutError:
        session._error = f"连接超时（{CONNECT_TIMEOUT}秒），请检查服务器地址"
        session._connected.clear()
        return
    except (OSError, websockets.InvalidURI) as e:
        logger.warning("连接中继失败: %s", e)
        session._error = "无法连接到中继服务器，请检查地址是否正确"
        session._connected.clear()
        return

    try:
        async with ws:
            session._connected.set()

            # 先启动收发循环，否则无法接收服务器的响应
            heartbeat = asyncio.create_task(_heartbeat_loop(session, ws))
            recv = asyncio.create_task(_recv_loop(session, ws))
            send = asyncio.create_task(_send_loop(session, ws))

            if create:
                await ws.send(json.dumps({"type": "create"}))
            else:
                await ws.send(json.dumps({"type": "join", "room": session._room_code}))

            # 等待匹配完成（带超时）
            try:
                await asyncio.wait_for(
                    _poll_event(session), timeout=MATCH_TIMEOUT
                )
            except asyncio.TimeoutError:
                if not session._started.is_set():
                    session._error = f"匹配超时（{MATCH_TIMEOUT}秒），未找到对手"
                    return
            except Exception:
                pass

            done, _ = await asyncio.wait(
                [recv, send, heartbeat],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in [recv, send, heartbeat]:
                if not t.done():
                    t.cancel()
    except (OSError, websockets.InvalidURI) as e:
        logger.warning("会话连接中断: %s", e)
        session._error = "与中继服务器的连接已中断"
    except asyncio.TimeoutError:
        session._error = "连接已超时"
    finally:
        session._connected.clear()
        session._started.clear()


async def _recv_loop(session: NetworkSession, ws) -> None:
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("收到无效 JSON: %.100s", raw)
                continue
            t = msg.get("type")
            if t == "created":
                session._room_code = msg.get("room", "")
            elif t == "start":
                session._player_id = msg.get("player", 0)
                session._started.set()
            elif t == "error":
                session._error = msg.get("msg", "服务器返回错误")
                session._inbox.put(msg)
            elif t == "pong":
                pass
            elif t in ("move", "opponent_left", "rematch", "rematch_accept"):
                session._inbox.put(msg)
    except websockets.ConnectionClosed:
        pass
    except Exception:
        logger.exception("_recv_loop 异常退出")
        session._error = "网络通信异常"


async def _heartbeat_loop(session: NetworkSession, ws) -> None:
    """定期发送 ping 保持连接。超时未收到 pong 则断开。"""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            try:
                pong_waiter = await ws.ping()
                await asyncio.wait_for(pong_waiter, timeout=HEARTBEAT_TIMEOUT)
            except asyncio.TimeoutError:
                session._error = "与服务器连接中断（心跳超时）"
                return
    except websockets.ConnectionClosed:
        pass


async def _send_loop(session: NetworkSession, ws) -> None:
    while True:
        try:
            msg = session._outbox.get_nowait()
        except queue.Empty:
            await asyncio.sleep(0.01)
            continue
        if msg.get("type") == "__close__":
            break
        await ws.send(json.dumps(msg))
