"""Lightweight routing server for an end-to-end encrypted chat application.

The server deliberately avoids handling plaintext messages. It only stores
cryptographic metadata that clients need to discover peers (e.g., public keys)
while relaying ciphertext payloads over WebSocket connections.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn


class PublicKeyRegistration(BaseModel):
    """Model representing a client's advertised public key."""

    user_id: str = Field(..., description="Unique identifier for the client")
    public_key: str = Field(
        ...,
        description=(
            "The client's public key encoded in a transport-friendly format "
            "(e.g., base64)."
        ),
    )


class MessageEnvelope(BaseModel):
    """Encrypted message metadata relayed by the server."""

    sender_id: str = Field(..., description="ID of the sender of the ciphertext")
    room_id: str = Field(..., description="Chat room identifier")
    ciphertext: str = Field(..., description="Encrypted payload destined for peers")
    nonce: str = Field(..., description="Nonce used during encryption")
    timestamp: int = Field(..., description="Client-side UNIX timestamp of the message")
    signature: str = Field(
        ..., description="Signature authenticating ciphertext + metadata"
    )


@dataclass
class ClientConnection:
    websocket: WebSocket
    room_id: str
    user_id: str


class ConnectionManager:
    """Tracks WebSocket connections and distributes ciphertext payloads."""

    def __init__(self) -> None:
        self._connections: Dict[str, ClientConnection] = {}
        self._rooms: Dict[str, Set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, room_id: str, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            if user_id in self._connections:
                raise HTTPException(status_code=409, detail="User already connected")
            await websocket.accept()
            self._connections[user_id] = ClientConnection(websocket, room_id, user_id)
            self._rooms[room_id].add(user_id)

    async def disconnect(self, user_id: str) -> None:
        async with self._lock:
            conn = self._connections.pop(user_id, None)
            if not conn:
                return
            self._rooms[conn.room_id].discard(user_id)
            if not self._rooms[conn.room_id]:
                self._rooms.pop(conn.room_id, None)

    async def broadcast(self, envelope: MessageEnvelope) -> None:
        async with self._lock:
            # Only deliver messages to other participants in the same room.
            recipient_ids = self._rooms.get(envelope.room_id, set()) - {envelope.sender_id}
            for recipient_id in recipient_ids:
                connection = self._connections.get(recipient_id)
                if connection:
                    await connection.websocket.send_json(envelope.dict())

    async def list_room_members(self, room_id: str) -> Set[str]:
        async with self._lock:
            return set(self._rooms.get(room_id, set()))


app = FastAPI(title="E2EE Chat Relay Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
public_keys: Dict[str, str] = {}


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Simple liveness probe."""

    return {"status": "ok"}


@app.post("/keys", status_code=201)
async def register_key(payload: PublicKeyRegistration) -> Dict[str, str]:
    """Register or update a client's public key."""

    public_keys[payload.user_id] = payload.public_key
    return {"message": "Public key registered"}


@app.get("/keys/{user_id}")
async def get_key(user_id: str) -> Dict[str, Optional[str]]:
    """Return the registered public key for a client if available."""

    return {"user_id": user_id, "public_key": public_keys.get(user_id)}


@app.get("/rooms/{room_id}/members")
async def room_members(room_id: str) -> Dict[str, Set[str]]:
    """List connected clients in a given chat room."""

    return {"members": await manager.list_room_members(room_id)}


@app.websocket("/ws/{room_id}/{user_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str, user_id: str) -> None:
    try:
        await manager.connect(room_id, user_id, websocket)
        while True:
            data = await websocket.receive_json()
            envelope = MessageEnvelope(**data)
            await manager.broadcast(envelope)
    except WebSocketDisconnect:
        await manager.disconnect(user_id)
    except HTTPException:
        # Re-raise to let FastAPI send an error response before accept
        raise
    except Exception:
        await websocket.close(code=1011)
        await manager.disconnect(user_id)
        raise


if __name__ == "__main__":  # pragma: no cover
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
