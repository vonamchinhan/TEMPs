"""Command line WebSocket client for the E2EE chat demo."""
from __future__ import annotations

import asyncio
import json
from typing import Dict

import websockets

from encryption import KeyPair, decrypt_message, derive_shared_key, encrypt_message


class ChatClient:
    def __init__(self, username: str, server_url: str) -> None:
        self.username = username
        self.server_url = server_url
        self.key_pair = KeyPair.generate()
        self.shared_keys: Dict[str, bytes] = {}

    async def send_handshake(self, websocket: websockets.WebSocketClientProtocol) -> None:
        message = {
            "type": "handshake",
            "username": self.username,
            "public_key": self.key_pair.serialize_public_key(),
        }
        await websocket.send(json.dumps(message))

    def add_peer(self, username: str, public_key_b64: str) -> None:
        if username == self.username:
            return
        peer_public_key = KeyPair.deserialize_public_key(public_key_b64)
        self.shared_keys[username] = derive_shared_key(self.key_pair.private_key, peer_public_key)
        print(f"\nĐã thiết lập khóa chung với {username}.")

    async def handle_incoming(self, websocket: websockets.WebSocketClientProtocol) -> None:
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            msg_type = message.get("type")
            if msg_type == "handshake":
                username = message.get("username")
                public_key = message.get("public_key")
                if username and public_key:
                    self.add_peer(username, public_key)
            elif msg_type == "system":
                print(f"\n[Hệ thống] {message.get('message')}")
            elif msg_type == "chat":
                sender = message.get("sender")
                if sender == self.username:
                    continue
                payloads = message.get("payloads", {})
                payload = payloads.get(self.username)
                if not payload:
                    continue
                key = self.shared_keys.get(sender)
                if not key:
                    print(f"\nKhông có khóa chung với {sender}.")
                    continue
                try:
                    plaintext = decrypt_message(key, payload["nonce"], payload["ciphertext"])
                except Exception:
                    print(f"\nKhông thể giải mã tin nhắn từ {sender}.")
                    continue
                print(f"\n{sender}: {plaintext}")
            print("> ", end="", flush=True)

    async def send_messages(self, websocket: websockets.WebSocketClientProtocol) -> None:
        loop = asyncio.get_event_loop()
        while True:
            text = await loop.run_in_executor(None, input, "> ")
            text = text.strip()
            if not text:
                continue
            if not self.shared_keys:
                print("Chưa có khóa chung với ai. Hãy đợi người khác kết nối.")
                continue
            payloads = {}
            for peer, key in self.shared_keys.items():
                nonce, ciphertext = encrypt_message(key, text)
                payloads[peer] = {"nonce": nonce, "ciphertext": ciphertext}
            message = {
                "type": "chat",
                "sender": self.username,
                "payloads": payloads,
            }
            await websocket.send(json.dumps(message))

    async def run(self) -> None:
        async with websockets.connect(self.server_url) as websocket:
            await self.send_handshake(websocket)
            print("Đã kết nối tới server. Gõ tin nhắn và nhấn Enter để gửi.")
            await asyncio.gather(
                self.handle_incoming(websocket),
                self.send_messages(websocket),
            )


def main() -> None:
    username = input("Nhập tên hiển thị: ").strip() or "user"
    server_url = input("Nhập URL server (mặc định ws://127.0.0.1:8765): ").strip()
    if not server_url:
        server_url = "ws://127.0.0.1:8765"
    client = ChatClient(username=username, server_url=server_url)
    try:
        asyncio.run(client.run())
    except KeyboardInterrupt:
        print("\nĐã thoát client.")


if __name__ == "__main__":
    main()
