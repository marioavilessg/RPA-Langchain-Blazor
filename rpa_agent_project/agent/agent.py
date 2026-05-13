from __future__ import annotations

import os
import warnings

from langchain_openai import ChatOpenAI
from shared.config import load_environment

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from langchain.agents import create_agent
    from langgraph.checkpoint.memory import MemorySaver

from agent.tools import extract_parameters, list_procedures, run_workflow, search_procedures


load_environment()

SYSTEM_PROMPT = """
Eres un agente autonomo que automatiza procedimientos RPA sobre formularios web locales.

Reglas:
- Usa las tools cuando una peticion requiera consultar, preparar o ejecutar un procedimiento.
- Para una alta de producto, busca primero el procedimiento con search_procedures.
- Usa extract_parameters con el texto original del usuario y el param_schema del procedimiento elegido.
- Si extract_parameters devuelve missing con valores, pregunta solo por esos datos y no llames a run_workflow.
- Llama a run_workflow solo cuando extract_parameters devuelva ok=true y missing=[].
- Si la peticion es ambigua, usa list_procedures o pide aclaracion.
- No inventes parametros obligatorios.
- Explica al usuario el resultado final en lenguaje natural, incluyendo si el RPA termino ok o con error.
""".strip()


llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL", "local-model"),
    base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:1234/v1"),
    api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),
    temperature=0,
)


agent = create_agent(
    model=llm,
    tools=[search_procedures, extract_parameters, run_workflow, list_procedures],
    system_prompt=SYSTEM_PROMPT,
    checkpointer=MemorySaver(),
)
