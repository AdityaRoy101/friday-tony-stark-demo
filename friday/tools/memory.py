"""
Memory tools - explicit, user-controlled assistant memory.
"""

import json
import os
from datetime import datetime
from pathlib import Path


def _memory_path() -> Path:
    configured = os.getenv("FRIDAY_MEMORY_PATH")
    if configured:
        return Path(configured).expanduser()

    base = os.getenv("LOCALAPPDATA")
    if base:
        return Path(base) / "FridayAgent" / "memory.json"
    return Path.home() / ".friday_agent" / "memory.json"


def _load_memory() -> dict:
    path = _memory_path()
    if not path.exists():
        return {"items": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"items": []}
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return {"items": []}
    return data


def _save_memory(data: dict) -> None:
    path = _memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_sensitive(text: str) -> bool:
    lowered = text.lower()
    blocked = ("password", "secret", "token", "api key", "apikey", "credential", "private key")
    return any(term in lowered for term in blocked)


def register(mcp):

    @mcp.tool()
    def remember_fact(key: str, value: str, category: str = "general") -> str:
        """
        Store an explicit user-approved memory item.
        Use only when the user asks to remember, save, or keep something.
        """
        key = key.strip()
        value = value.strip()
        category = (category or "general").strip()[:40]

        if not key or not value:
            return "Memory needs both a key and a value."
        if _is_sensitive(key) or _is_sensitive(value):
            return "I will not store secrets, passwords, tokens, or credentials in memory."

        data = _load_memory()
        now = datetime.now().astimezone().isoformat()
        items = data["items"]
        for item in items:
            if item.get("key", "").lower() == key.lower():
                item.update({"value": value, "category": category, "updated_at": now})
                _save_memory(data)
                return f"Updated memory: {key}"

        items.append({"key": key, "value": value, "category": category, "updated_at": now})
        _save_memory(data)
        return f"Remembered: {key}"

    @mcp.tool()
    def recall_memory(query: str = "", max_items: int = 8) -> str:
        """
        Recall visible memory items.
        Use when the user asks what you remember or asks about saved preferences.
        """
        query = (query or "").strip().lower()
        max_items = max(1, min(max_items, 20))
        items = _load_memory()["items"]

        if query:
            items = [
                item for item in items
                if query in item.get("key", "").lower()
                or query in item.get("value", "").lower()
                or query in item.get("category", "").lower()
            ]

        if not items:
            return "No matching memory found."

        lines = ["VISIBLE MEMORY"]
        for item in items[:max_items]:
            category = item.get("category", "general")
            lines.append(f"- [{category}] {item.get('key')}: {item.get('value')}")
        return "\n".join(lines)

    @mcp.tool()
    def forget_memory(key: str) -> str:
        """Delete a memory item by key when the user asks to forget it."""
        key = key.strip()
        data = _load_memory()
        before = len(data["items"])
        data["items"] = [item for item in data["items"] if item.get("key", "").lower() != key.lower()]
        if len(data["items"]) == before:
            return f"No memory found for: {key}"
        _save_memory(data)
        return f"Forgot: {key}"

