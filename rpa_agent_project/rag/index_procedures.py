from __future__ import annotations

import json
import shutil
import warnings
from pathlib import Path
from typing import Any

from langchain_core._api.deprecation import LangChainDeprecationWarning
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document


warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)

BASE_DIR = Path(__file__).resolve().parents[1]
PROCEDURES_PATH = BASE_DIR / "procedures"
DB_PATH = BASE_DIR / "rag" / "chroma_db"


def _schema_to_text(schema: dict[str, Any]) -> str:
    lines = []
    for name, spec in schema.items():
        if isinstance(spec, dict):
            values = spec.get("values")
            values_text = f" Valores: {', '.join(values)}." if values else ""
            lines.append(
                f"- {name}: {spec.get('type', 'string')}. "
                f"{spec.get('description', '')}.{values_text}"
            )
        else:
            lines.append(f"- {name}: {spec}")
    return "\n".join(lines)


def load_procedures() -> tuple[list[Document], list[str]]:
    docs: list[Document] = []
    ids: list[str] = []

    for file in sorted(PROCEDURES_PATH.glob("*.json")):
        with file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        workflow_id = data["id"]
        schema = data.get("param_schema", {})
        tags = data.get("tags", [])
        content = f"""
Titulo: {data.get("titulo", "")}
Descripcion: {data.get("descripcion", "")}
Aplicacion: {data.get("app", "")}
Tags: {", ".join(tags)}
Parametros:
{_schema_to_text(schema)}
""".strip()

        docs.append(
            Document(
                page_content=content,
                metadata={
                    "id": workflow_id,
                    "titulo": data.get("titulo", workflow_id),
                    "descripcion": data.get("descripcion", ""),
                    "app": data.get("app", ""),
                    "tags": json.dumps(tags, ensure_ascii=True),
                    "param_schema": json.dumps(schema, ensure_ascii=True),
                },
            )
        )
        ids.append(workflow_id)

    return docs, ids


def reset_db() -> None:
    if not DB_PATH.exists():
        return

    base = BASE_DIR.resolve()
    db = DB_PATH.resolve()
    if not db.is_relative_to(base):
        raise RuntimeError(f"Ruta de Chroma fuera del proyecto: {db}")

    shutil.rmtree(db)


def index() -> None:
    print("[RAG] Cargando embeddings...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    print("[RAG] Cargando procedimientos...")
    docs, ids = load_procedures()

    if not docs:
        print("[RAG] No hay procedimientos para indexar")
        return

    reset_db()
    print(f"[RAG] Indexando {len(docs)} procedimiento(s)...")

    db = Chroma.from_documents(
        docs,
        embeddings,
        ids=ids,
        persist_directory=str(DB_PATH),
    )

    print(f"[RAG] Indexado correctamente en {DB_PATH}")


if __name__ == "__main__":
    index()
