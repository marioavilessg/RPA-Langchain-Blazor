from __future__ import annotations

import json
import os
import re
import unicodedata
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain.tools import tool
from langchain_core._api.deprecation import LangChainDeprecationWarning
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI

from agent.runner import run_workflow as execute_workflow
from shared.config import load_environment


warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)
load_environment()

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "rag" / "chroma_db"


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=True, indent=2)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    without_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return without_accents.lower()


def _loads_if_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _coerce_schema(param_schema: Any) -> dict[str, Any]:
    param_schema = _loads_if_json(param_schema)
    return param_schema if isinstance(param_schema, dict) else {}


def _required_fields(schema: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    for name, spec in schema.items():
        if not isinstance(spec, dict) or spec.get("required", True):
            fields.append(name)
    return fields


def _enum_values(schema: dict[str, Any], field: str) -> list[str]:
    spec = schema.get(field)
    if isinstance(spec, dict) and isinstance(spec.get("values"), list):
        return [str(value) for value in spec["values"]]
    return []


def _parse_markdown_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", cleaned, flags=re.I | re.S)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    object_match = re.search(r"\{.*\}", cleaned, flags=re.S)
    if object_match:
        cleaned = object_match.group(0)

    parsed = json.loads(cleaned)
    return parsed if isinstance(parsed, dict) else {}


@lru_cache(maxsize=1)
def _embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def _db() -> Chroma:
    return Chroma(persist_directory=str(DB_PATH), embedding_function=_embeddings())


@lru_cache(maxsize=1)
def _llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "local-model"),
        base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),
        temperature=0,
    )


def _procedure_from_metadata(metadata: dict[str, Any], score: float | None = None) -> dict[str, Any]:
    procedure = {
        "id": metadata.get("id"),
        "titulo": metadata.get("titulo", metadata.get("id")),
        "descripcion": metadata.get("descripcion", ""),
        "app": metadata.get("app", ""),
        "param_schema": _loads_if_json(metadata.get("param_schema", {})),
    }
    if score is not None:
        procedure["score"] = score
    return procedure


@tool
def search_procedures(query: str, top_k: int = 3) -> dict[str, Any]:
    """
    Busca procedimientos RPA en ChromaDB a partir de una peticion en lenguaje natural.
    Usala antes de ejecutar automatizaciones para elegir el workflow correcto.
    Devuelve resultados con id, titulo, descripcion, score y param_schema.
    """
    print(f"[TOOL] search_procedures(query={query!r}, top_k={top_k})")
    if not DB_PATH.exists():
        return {"ok": False, "results": [], "error": f"No existe la base RAG en {DB_PATH}"}

    top_k = max(1, min(int(top_k), 10))
    docs = _db().similarity_search_with_score(query, k=top_k)
    results = []
    for doc, distance in docs:
        score = round(1 / (1 + float(distance)), 4)
        item = _procedure_from_metadata(dict(doc.metadata), score=score)
        item["raw_distance"] = round(float(distance), 4)
        results.append(item)

    response = {"ok": bool(results), "results": results}
    print(f"[TOOL] search_procedures -> {_json(response)}")
    return response


@tool
def list_procedures() -> dict[str, Any]:
    """
    Lista los procedimientos indexados en ChromaDB.
    Usala si la peticion del usuario es ambigua o necesitas orientarte antes de buscar.
    """
    print("[TOOL] list_procedures()")
    if not DB_PATH.exists():
        return {"ok": False, "procedures": [], "error": f"No existe la base RAG en {DB_PATH}"}

    data = _db().get(include=["metadatas"])
    procedures = [_procedure_from_metadata(dict(metadata)) for metadata in data.get("metadatas", [])]
    response = {"ok": True, "procedures": procedures}
    print(f"[TOOL] list_procedures -> {_json(response)}")
    return response


def _deterministic_extract(text: str, schema: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize(text)
    params: dict[str, Any] = {}

    price_patterns = [
        r"(?:precio|vale|cuesta)\s*[:=]?\s*(\d+(?:[.,]\d+)?)",
        r"(\d+(?:[.,]\d+)?)\s*(?:eur|euros?|€)",
    ]
    for pattern in price_patterns:
        match = re.search(pattern, normalized)
        if match:
            params["precio"] = float(match.group(1).replace(",", "."))
            break

    stock_patterns = [
        r"(?:stock|cantidad)\s*[:=]?\s*(\d+)",
        r"(\d+)\s*(?:unidades|uds)\b",
    ]
    for pattern in stock_patterns:
        match = re.search(pattern, normalized)
        if match:
            params["stock"] = int(match.group(1))
            break

    category_values = _enum_values(schema, "categoria")
    if category_values:
        normalized_values = {_normalize(value): value for value in category_values}
        for normalized_value, original_value in normalized_values.items():
            if re.search(rf"\b{re.escape(normalized_value)}\b", normalized):
                params["categoria"] = original_value
                break
    else:
        match = re.search(r"categoria\s*[:=]?\s*([a-z0-9_-]+)", normalized)
        if match:
            params["categoria"] = match.group(1)

    name = _extract_name(text)
    if name:
        params["nombre"] = name

    return params


def _extract_name(text: str) -> str | None:
    candidate = text.strip()
    candidate = re.sub(
        r"^\s*(?:"
        r"dame\s+de\s+alta\s+un\s+producto|"
        r"da\s+de\s+alta\s+un\s+producto|"
        r"dar\s+de\s+alta\s+un\s+producto|"
        r"quiero\s+dar\s+de\s+alta\s+un\s+producto|"
        r"alta\s+producto|"
        r"crear\s+producto|"
        r"nuevo\s+producto|"
        r"producto"
        r")\s*:?\s*",
        "",
        candidate,
        flags=re.I,
    )
    candidate = re.split(
        r"\s*,?\s*(?:precio|stock|categor[ií]a)\b|"
        r"\d+(?:[.,]\d+)?\s*(?:€|eur|euros?)|"
        r"\d+\s*(?:unidades|uds)\b",
        candidate,
        maxsplit=1,
        flags=re.I,
    )[0]
    candidate = re.sub(r"\s+", " ", candidate).strip(" ,:-")

    if not candidate:
        return None
    if _normalize(candidate) in {"dame de alta", "alta", "producto", "crear"}:
        return None
    return candidate


def _merge_llm_result(
    current: dict[str, Any],
    text: str,
    schema: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    required = _required_fields(schema)
    if all(field in current and current[field] not in (None, "") for field in required):
        return current, None

    prompt = f"""
Extrae parametros para ejecutar un workflow RPA.

Texto del usuario:
{text}

Schema esperado:
{json.dumps(schema, ensure_ascii=True, indent=2)}

Devuelve solo un objeto JSON. Usa null si falta un valor. No anadas explicaciones.
""".strip()

    try:
        raw_response = _llm().invoke(prompt).content
        parsed = _parse_markdown_json(raw_response)
    except Exception as exc:
        return current, f"LLM no disponible o respuesta invalida: {type(exc).__name__}: {exc}"

    params = dict(current)
    for key, value in parsed.items():
        if key not in params and value not in (None, ""):
            params[key] = value
    return params, raw_response


def _validate_params(params: dict[str, Any], schema: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    validated: dict[str, Any] = {}

    if params.get("nombre"):
        validated["nombre"] = str(params["nombre"]).strip()

    if params.get("precio") not in (None, ""):
        try:
            validated["precio"] = float(str(params["precio"]).replace(",", "."))
        except ValueError:
            pass

    if params.get("stock") not in (None, ""):
        try:
            validated["stock"] = int(float(str(params["stock"]).replace(",", ".")))
        except ValueError:
            pass

    if params.get("categoria"):
        category = str(params["categoria"]).strip()
        values = _enum_values(schema, "categoria")
        if values:
            value_by_normalized = {_normalize(value): value for value in values}
            normalized = _normalize(category)
            if normalized in value_by_normalized:
                validated["categoria"] = value_by_normalized[normalized]
        else:
            validated["categoria"] = category

    missing = [
        field
        for field in _required_fields(schema)
        if field not in validated or validated[field] in (None, "")
    ]
    return validated, missing


@tool
def extract_parameters(text: str, param_schema: dict[str, Any]) -> dict[str, Any]:
    """
    Extrae parametros desde texto libre usando el schema del procedimiento elegido.
    Devuelve ok, params, missing y raw. Si missing no esta vacio, el agente debe pedir esos datos
    y no debe ejecutar el workflow todavia.
    """
    print(f"[TOOL] extract_parameters(text={text!r}, param_schema={_json(param_schema)})")
    schema = _coerce_schema(param_schema)
    extracted = _deterministic_extract(text, schema)
    merged, raw = _merge_llm_result(extracted, text, schema)
    params, missing = _validate_params(merged, schema)

    response = {
        "ok": not missing,
        "params": params,
        "missing": missing,
        "raw": {
            "deterministic": extracted,
            "llm": raw,
        },
    }
    print(f"[TOOL] extract_parameters -> {_json(response)}")
    return response


@tool
def run_workflow(workflow_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """
    Ejecuta un workflow RPA por id usando los parametros ya extraidos y validados.
    Usala solo cuando extract_parameters devuelva ok=true y missing=[].
    Devuelve ok, duracion, ultimo texto observado y error si la automatizacion falla.
    """
    print(f"[TOOL] run_workflow(workflow_id={workflow_id!r}, params={_json(params)})")
    params = _loads_if_json(params)
    if not isinstance(params, dict):
        return {"ok": False, "error": "params debe ser un objeto JSON"}

    result = execute_workflow(workflow_id, params)
    print(f"[TOOL] run_workflow -> {_json(result)}")
    return result
