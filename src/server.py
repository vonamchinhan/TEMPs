"""WebSocket relay server for the end-to-end encrypted chat demo."""
from __future__ import annotations

import asyncio
import json
from typing import Dict, Set

import websockets
from websockets.server import WebSocketServerProtocol


class ChatServer:
    def __init__(self) -> None:
        self.clients: Set[WebSocketServerProtocol] = set()
        self.usernames: Dict[WebSocketServerProtocol, str] = {}
        self.handshakes: Dict[str, Dict] = {}

    async def register(self, websocket: WebSocketServerProtocol) -> None:
        self.clients.add(websocket)
        self.usernames[websocket] = ""
        # Gửi lại các handshake đã lưu cho client mới.
        for handshake in self.handshakes.values():
            await websocket.send(json.dumps(handshake))

    async def unregister(self, websocket: WebSocketServerProtocol) -> None:
        username = self.usernames.get(websocket, "")
        self.clients.discard(websocket)
        self.usernames.pop(websocket, None)
        if username and username in self.handshakes:
            self.handshakes.pop(username)
            await self.broadcast(
                {
                    "type": "system",
                    "message": f"{username} đã thoát khỏi phòng.",
                }
            )
        else:
            await self.broadcast(
                {
                    "type": "system",
                    "message": "Một người dùng đã thoát khỏi phòng.",
                }
            )

    async def broadcast(self, message: Dict) -> None:
        if not self.clients:
            return
        data = json.dumps(message)
        await asyncio.gather(
            *[client.send(data) for client in self.clients],
            return_exceptions=True,
        )

    async def handle(self, websocket: WebSocketServerProtocol) -> None:
        await self.register(websocket)
        try:
            async for raw_message in websocket:
                try:
                    message = json.loads(raw_message)
                except json.JSONDecodeError:
                    continue

                msg_type = message.get("type")
                if msg_type == "handshake":
                    username = message.get("username", "")
                    self.usernames[websocket] = username
                    if username:
                        self.handshakes[username] = message
                        await self.broadcast(message)
                elif msg_type == "chat":
                    await self.broadcast(message)
                elif msg_type == "system":
                    await self.broadcast(message)
        finally:
            await self.unregister(websocket)


async def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    server = ChatServer()
    async with websockets.serve(server.handle, host, port):
        print(f"Server đang lắng nghe tại ws://{host}:{port}")
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Server đã tắt.")
