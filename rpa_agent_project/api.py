from __future__ import annotations

import json
import os
import sys
import unicodedata
import uuid
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from agent.agent import agent
from agent.tools import check_runtime_services
from shared.config import load_environment


load_environment()

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


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


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    without_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return without_accents.lower()


def _is_runtime_status_request(message: str) -> bool:
    normalized = _normalize(message)
    status_terms = (
        "api",
        "formulario",
        "health",
        "puerto",
        "servicio",
        "entorno",
    )
    action_terms = (
        "comprueba",
        "comprobar",
        "estado",
        "disponible",
        "disponibilidad",
        "funciona",
        "funcionando",
        "conectado",
        "conectada",
        "responde",
    )
    return any(term in normalized for term in status_terms) and any(term in normalized for term in action_terms)


def _format_runtime_status(result: dict[str, Any]) -> str:
    checks = result.get("checks", [])
    lines = ["Estado del entorno:"]

    for check in checks:
        name = check.get("name", "Servicio")
        target = check.get("url") or check.get("path") or "sin ruta"
        ok = bool(check.get("ok"))
        status = "disponible" if ok else "no disponible"

        detail_parts = []
        if check.get("status_code") is not None:
            detail_parts.append(f"HTTP {check['status_code']}")
        if check.get("latency_ms") is not None:
            detail_parts.append(f"{check['latency_ms']} ms")
        if check.get("error"):
            detail_parts.append(str(check["error"]))

        detail = f" ({', '.join(detail_parts)})" if detail_parts else ""
        lines.append(f"- {name}: {status} en {target}{detail}.")

    if result.get("ok"):
        lines.append("Todo esta listo para ejecutar el flujo RPA.")
    else:
        lines.append("Revisa los servicios marcados como no disponibles antes de ejecutar el workflow.")

    return "\n".join(lines)


def _trace_message(message: Any) -> str | None:
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


def run_agent_turn(message: str, session_id: str) -> str:
    if _is_runtime_status_request(message):
        result = check_runtime_services.invoke({})
        return _format_runtime_status(result)

    config = {"configurable": {"thread_id": session_id}}
    seen_message_ids: set[str] = set()
    final_text = ""

    for event in agent.stream(
        {"messages": [("user", message)]},
        config=config,
        stream_mode="values",
    ):
        messages = event.get("messages", []) if isinstance(event, dict) else []
        for item in messages:
            message_id = getattr(item, "id", None)
            if not message_id:
                message_id = f"{getattr(item, 'type', '')}:{hash(_safe_text(getattr(item, 'content', '')))}"
            if message_id in seen_message_ids:
                continue
            seen_message_ids.add(message_id)

            possible_final = _trace_message(item)
            if possible_final:
                final_text = possible_final

    return final_text or "No se obtuvo respuesta del agente."


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class ChatResponse(BaseModel):
    ok: bool
    session_id: str
    response: str
    error: str | None = None


app = FastAPI(title="RPA Agent API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5049",
        "https://localhost:7295",
        "http://127.0.0.1:5049",
        "https://127.0.0.1:7295",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    session_id = request.session_id or f"rpa-chat-{uuid.uuid4()}"
    try:
        print(f"[API] Mensaje recibido session_id={session_id}: {request.message}")
        response = run_agent_turn(request.message, session_id)
        return ChatResponse(ok=True, session_id=session_id, response=response)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        print(f"[API] Error: {error}")
        return ChatResponse(ok=False, session_id=session_id, response="", error=error)


if __name__ == "__main__":
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("api:app", host="127.0.0.1", port=port, reload=False)
