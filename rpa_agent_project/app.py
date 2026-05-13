from __future__ import annotations

import json
import sys
import uuid
from typing import Any

from agent.agent import agent


def _safe_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", item)))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _compact_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=True)
    except TypeError:
        return str(value)


def _print_message(message: Any) -> str | None:
    message_type = getattr(message, "type", "")
    tool_calls = getattr(message, "tool_calls", None) or []

    if tool_calls:
        for call in tool_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "tool")
            args = call.get("args") if isinstance(call, dict) else getattr(call, "args", {})
            print(f"[AGENTE] Tool call: {name}({_compact_json(args)})")
        return None

    if message_type == "tool":
        tool_name = getattr(message, "name", "tool")
        print(f"[TOOL] Resultado {tool_name}: {_safe_text(getattr(message, 'content', ''))}")
        return None

    if message_type == "ai":
        content = _safe_text(getattr(message, "content", "")).strip()
        if content:
            return content

    return None


def run_turn(user_input: str, thread_id: str, seen_message_ids: set[str]) -> None:
    config = {"configurable": {"thread_id": thread_id}}
    final_text = None

    for event in agent.stream(
        {"messages": [("user", user_input)]},
        config=config,
        stream_mode="values",
    ):
        messages = event.get("messages", []) if isinstance(event, dict) else []
        for message in messages:
            message_id = getattr(message, "id", None)
            if not message_id:
                message_id = f"{getattr(message, 'type', '')}:{hash(_safe_text(getattr(message, 'content', '')))}"
            if message_id in seen_message_ids:
                continue
            seen_message_ids.add(message_id)

            possible_final = _print_message(message)
            if possible_final:
                final_text = possible_final

    if final_text:
        print(f"\nAgente: {final_text}\n")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    thread_id = f"rpa-session-{uuid.uuid4()}"
    seen_message_ids: set[str] = set()

    if len(sys.argv) > 1:
        run_turn(" ".join(sys.argv[1:]), thread_id, seen_message_ids)
        return

    print("Agente RPA listo. Escribe una peticion o 'salir'.")
    while True:
        try:
            user_input = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo.")
            return

        if not user_input:
            continue
        if user_input.lower() in {"salir", "exit", "quit"}:
            print("Saliendo.")
            return

        try:
            run_turn(user_input, thread_id, seen_message_ids)
        except Exception as exc:
            print(f"[ERROR] {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
