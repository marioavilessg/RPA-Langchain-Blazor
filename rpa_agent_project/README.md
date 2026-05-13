# Practica RPA + RAG con LangChain y LangGraph

Proyecto de agente autonomo que usa tools para buscar procedimientos RPA en ChromaDB, extraer parametros desde lenguaje natural y ejecutar un workflow con Playwright sobre un formulario web local.

## Arquitectura

```text
Usuario -> app.py chat CLI
       -> agent/agent.py create_agent + MemorySaver
       -> tools:
          - search_procedures: consulta ChromaDB
          - extract_parameters: extrae parametros con schema
          - run_workflow: ejecuta Playwright
          - list_procedures: lista procedimientos indexados
       -> procedures/*.json -> agent/runner.py -> web_form/index.html
```

## Eleccion LangChain vs LangGraph

La implementacion principal usa `langchain.agents.create_agent` porque la parte base de la practica acepta LangChain 1.x y esta API deja claro que el agente, y no `app.py`, decide cuando invocar las tools. `app.py` solo crea una sesion, pasa los mensajes al agente y muestra las trazas.

En LangChain 1.x, `create_agent` compila internamente un grafo de LangGraph. Por eso el objeto creado en `agent/agent.py` es un `CompiledStateGraph` y permite conectar `MemorySaver` como checkpointer con un `thread_id` estable para mantener una conversacion multi-turno.

La alternativa `langgraph.prebuilt.create_react_agent` o un `StateGraph` escrito a mano seria mas adecuada si se quisieran separar nodos explicitos de busqueda RAG, validacion, confirmacion humana y ejecucion RPA. En esta entrega se prioriza `create_agent` para mantener el agente reactivo con tool calling y se usa LangGraph para la memoria y el runtime interno.

## Instalacion

Desde esta carpeta:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
```

El modelo debe estar disponible mediante una API compatible con OpenAI. El proyecto carga automaticamente el archivo `.env` de la raiz:

```env
OPENAI_BASE_URL=http://localhost:1234/v1
OPENAI_API_KEY=lm-studio
OPENAI_MODEL=local-model
RPA_HEADLESS=0
WEB_FORM_PORT=8081
API_PORT=8000
```

Si quieres sobrescribirlo solo para una terminal, puedes usar variables de PowerShell:

```powershell
$env:OPENAI_BASE_URL="http://localhost:1234/v1"
$env:OPENAI_API_KEY="lm-studio"
$env:OPENAI_MODEL="local-model"
```

## Uso

Arranca el formulario web en una terminal:

```powershell
.\venv\Scripts\activate
python web_form\server.py
```

Por defecto se sirve en `http://localhost:8081`. Puedes cambiarlo con:

```powershell
$env:WEB_FORM_PORT="8081"
```

Indexa los procedimientos en ChromaDB:

```powershell
.\venv\Scripts\activate
python rag\index_procedures.py
python rag\test_query.py
```

Ejecuta el chat:

```powershell
python app.py
```

Tambien puedes exponer el agente por HTTP para usarlo desde la app Blazor:

```powershell
python api.py
```

La API queda en `http://localhost:8000` y ofrece `GET /health` y `POST /chat`.

Prompt de demo:

```text
Dame de alta un producto: Camiseta Negra Roma, precio 19.99, stock 25, categoria camisetas
```

Tambien puedes lanzar una unica peticion:

```powershell
python app.py "Dame de alta un producto: Camiseta Negra Roma, precio 19.99, stock 25, categoria camisetas"
```

## Recorder

`web_form/index.html` incluye un panel Recorder con Start, Stop y Download JSON. Graba clicks, inputs y selects con selectores CSS, sustituye valores por placeholders `{{nombre}}`, `{{precio}}`, `{{stock}}`, `{{categoria}}`, y descarga `alta_producto_v1.workflow.json`.

## Variables utiles

- `OPENAI_BASE_URL`: URL de la API compatible con OpenAI.
- `OPENAI_API_KEY`: clave para el proveedor local/remoto.
- `OPENAI_MODEL`: modelo con tool calling.
- `FORM_URL`: sobrescribe la URL del workflow si quieres apuntar a otro formulario.
- `RPA_HEADLESS=1`: ejecuta Playwright sin ventana visible.
- `WEB_FORM_PORT`: puerto del formulario local.
- `API_PORT`: puerto de la API FastAPI para Blazor.
