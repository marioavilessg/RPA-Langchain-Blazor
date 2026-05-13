# Practica RPA + RAG + LangChain + MAUI

Proyecto organizado como monorepo para entregar la practica completa.

## Estructura

```text
Practica-RPA-RAG-MAUI/
|-- rpa_agent_project/   # Backend Python: RPA, LangChain, RAG, Chroma y API
|-- maui_app/            # Aplicacion MAUI Blazor Hybrid
|-- README.md            # Guia general
|-- .gitignore
```

## 1. Backend Python

```powershell
cd rpa_agent_project
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Antes de usar el agente, indexa los procedimientos:

```powershell
python rag\index_procedures.py
```

## 2. LM Studio

Abre LM Studio y deja un modelo de chat cargado con servidor compatible con OpenAI en:

```text
http://localhost:1234/v1
```

El modelo debe soportar tool calling para que el agente pueda llamar a las tools. No basta con tener cargado solo un modelo de embeddings como `text-embedding-nomic-embed-text-v1.5`.

Puedes comprobar que el servidor responde con:

```powershell
Invoke-WebRequest http://localhost:1234/v1/models
```

## 3. Orden de arranque

Usa terminales separadas para mantener vivos los servicios:

Terminal 1: LM Studio

```text
Servidor OpenAI-compatible en http://localhost:1234/v1 con un modelo de chat/tool-calling cargado.
```

Terminal 2: formulario web local

```powershell
cd rpa_agent_project
.\venv\Scripts\activate
python web_form\server.py
```

El formulario queda en:

```text
http://localhost:8081
```

Terminal 3: API Python

```powershell
cd rpa_agent_project
.\venv\Scripts\activate
python api.py
```

La API queda en:

```text
http://127.0.0.1:8000
```

Puedes comprobarla con:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

Terminal 4: aplicacion MAUI

```powershell
cd maui_app
dotnet build .\RPAChat.App\RPAChat.App.csproj -t:Run -f net9.0-windows10.0.19041.0
```

La app llama a la API Python en:

```text
http://127.0.0.1:8000
```

## Demo

Mensaje de prueba:

```text
Dame de alta un producto: Camiseta Negra Roma, precio 19.99, stock 25, categoria camisetas
```

El flujo esperado es:

1. El agente busca el procedimiento con RAG.
2. Extrae los parametros del texto.
3. Ejecuta el workflow RPA.
4. El formulario muestra el mensaje de guardado.

## Notas para GitHub

No se suben archivos locales como `.env`, `venv`, `bin`, `obj` ni la base generada de Chroma. Si otra persona clona el proyecto, debe crear su propio `.env` copiando `.env.example`.
