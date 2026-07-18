"""Recent chat memory cho query rewrite.

Redis la session store, khong phai legal vector store. Khi chua cau hinh Redis,
local dev dung in-memory store; production phai truyen REDIS_URL.
"""

from __future__ import annotations

import json
import threading
from collections import defaultdict

import config


class ChatMemory:
    def recent(self, thread_id: str, limit: int) -> list[dict[str, str]]:
        raise NotImplementedError

    def append(self, thread_id: str, role: str, content: str) -> None:
        raise NotImplementedError


class InMemoryChatMemory(ChatMemory):
    def __init__(self) -> None:
        self._messages: dict[str, list[dict[str, str]]] = defaultdict(list)
        self._lock = threading.Lock()

    def recent(self, thread_id: str, limit: int) -> list[dict[str, str]]:
        with self._lock:
            return list(self._messages.get(thread_id, [])[-limit:])

    def append(self, thread_id: str, role: str, content: str) -> None:
        with self._lock:
            rows = self._messages[thread_id]
            rows.append({"role": role, "content": content})
            del rows[:-config.CHAT_STORED_MESSAGES]


class RedisChatMemory(ChatMemory):
    def __init__(self, url: str) -> None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Thieu package redis") from exc
        self.client = redis.Redis.from_url(url, decode_responses=True)

    @staticmethod
    def _key(thread_id: str) -> str:
        return f"grandpilot:chat:{thread_id}:messages"

    def recent(self, thread_id: str, limit: int) -> list[dict[str, str]]:
        rows = self.client.lrange(self._key(thread_id), -limit, -1)
        return [json.loads(row) for row in rows]

    def append(self, thread_id: str, role: str, content: str) -> None:
        key = self._key(thread_id)
        payload = json.dumps({"role": role, "content": content}, ensure_ascii=False)
        with self.client.pipeline() as pipe:
            pipe.rpush(key, payload)
            pipe.ltrim(key, -config.CHAT_STORED_MESSAGES, -1)
            pipe.expire(key, config.CHAT_MEMORY_TTL_SECONDS)
            pipe.execute()


def build_chat_memory() -> ChatMemory:
    if config.REDIS_URL:
        return RedisChatMemory(config.REDIS_URL)
    return InMemoryChatMemory()
