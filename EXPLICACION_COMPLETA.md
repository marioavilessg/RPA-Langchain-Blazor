# Documentación técnica del proyecto

Esta guía explica en detalle los dos componentes del repositorio:

- `rpa_agent_project`: backend Python con agente LangChain, RAG, API FastAPI, Playwright y formulario web.
- `maui_app`: aplicacion .NET MAUI Blazor Hybrid que funciona como interfaz de chat.

La idea principal del trabajo es demostrar una automatizacion RPA controlada por lenguaje natural. El usuario escribe una peticion en la app MAUI, la app llama a una API Python, el agente busca el procedimiento adecuado con RAG, extrae parametros, ejecuta un workflow con Playwright y devuelve el resultado al chat.

## 1. Resumen del sistema

```text
Usuario
  |
  v
MAUI Blazor App
  |
  | POST /chat
  v
FastAPI Python
  |
  v
Agente LangChain/LangGraph
  |
  +-- search_procedures -> ChromaDB/RAG
  +-- extract_parameters -> reglas + LLM local
  +-- run_workflow -> Playwright
  |
  v
Formulario web local
```

El proyecto combina cuatro ideas:

- RPA: automatizar acciones sobre una interfaz web.
- RAG: buscar procedimientos almacenados en una base vectorial.
- Agente con tools: el modelo decide que herramienta usar en cada paso.
- MAUI: interfaz de escritorio/multiplataforma para hablar con el agente.

## 2. Proyecto Python: `rpa_agent_project`

Este proyecto es el cerebro de la practica. Contiene el agente, la API, el formulario web, la base RAG y el ejecutor RPA.

### 2.1. Archivos principales

`api.py`

- Levanta una API con FastAPI en `http://127.0.0.1:8000`.
- Expone `GET /health` para comprobar que esta viva.
- Expone `POST /chat` para recibir mensajes desde MAUI.
- Crea o recibe un `session_id`.
- Llama al agente con `run_agent_turn`.
- Devuelve un JSON con `ok`, `session_id`, `response` y `error`.

`app.py`

- Version de consola del agente.
- Sirve para probar el backend sin abrir MAUI.
- Permite escribir mensajes directamente en terminal.

`agent/agent.py`

- Configura el agente principal.
- Usa `ChatOpenAI` apuntando a LM Studio en `http://localhost:1234/v1`.
- Define el `SYSTEM_PROMPT`, que obliga al agente a seguir este orden:
  1. Buscar procedimiento con `search_procedures`.
  2. Extraer parametros con `extract_parameters`.
  3. Si faltan datos, preguntar al usuario.
  4. Si estan todos, ejecutar `run_workflow`.
- Registra las tools disponibles:
  - `search_procedures`
  - `extract_parameters`
  - `run_workflow`
  - `list_procedures`

`agent/tools.py`

- Contiene las herramientas que puede usar el agente.
- `search_procedures`: consulta ChromaDB para encontrar el procedimiento mas parecido a la peticion.
- `list_procedures`: lista los procedimientos indexados.
- `extract_parameters`: extrae nombre, precio, stock y categoria desde texto libre.
- `run_workflow`: ejecuta el procedimiento RPA si los parametros son validos.

`agent/runner.py`

- Es el motor RPA.
- Lee un workflow JSON.
- Abre Chromium con Playwright.
- Navega al formulario local.
- Ejecuta pasos como `type`, `select`, `click` y `wait_for_text`.
- Devuelve un resultado estructurado con `ok`, duracion, texto final y error si ocurre.

`procedures/alta_producto.json`

- Es el procedimiento RPA de ejemplo.
- Define:
  - `id`: `alta_producto`
  - descripcion del proceso
  - URL del formulario
  - parametros obligatorios
  - pasos de automatizacion
- Campos requeridos:
  - `nombre`
  - `precio`
  - `stock`
  - `categoria`

`rag/index_procedures.py`

- Convierte los JSON de `procedures` en documentos.
- Genera embeddings con `all-MiniLM-L6-v2`.
- Guarda la base vectorial en `rag/chroma_db`.
- Hay que ejecutarlo antes de usar el RAG.

`web_form/server.py`

- Sirve el formulario local en `http://localhost:8081`.
- Usa un servidor HTTP simple de Python.

`web_form/index.html`

- Es el formulario que automatiza Playwright.
- Tiene campos con IDs importantes:
  - `nombre`
  - `precio`
  - `stock`
  - `categoria`
  - `btn_guardar`
  - `toast`
- Tambien incluye un recorder para grabar pasos y exportar JSON.

`shared/config.py`

- Carga variables desde `.env`.
- Permite configurar LM Studio, puertos y modo headless.

`shared/templating.py`

- Sustituye placeholders como `{{nombre}}` por valores reales.
- Esto permite que el JSON del workflow sea reutilizable.

### 2.2. Variables importantes

El archivo `.env` configura el entorno. Valores esperados:

```text
OPENAI_BASE_URL=http://localhost:1234/v1
OPENAI_API_KEY=lm-studio
OPENAI_MODEL=local-model
FORM_URL=http://localhost:8081
API_PORT=8000
WEB_FORM_PORT=8081
RPA_HEADLESS=false
```

El modelo no está alojado en la nube: se usa LM Studio como servidor local compatible con OpenAI API.

### 2.3. Flujo interno del backend

Cuando llega esta frase:

```text
Alta producto Camiseta Negra Roma, precio 19.99, stock 25, categoria camisetas
```

Pasa esto:

1. MAUI envia el texto a `POST /chat`.
2. `api.py` llama al agente.
3. El agente usa `search_procedures` para buscar un workflow relacionado con "alta producto".
4. ChromaDB devuelve `alta_producto`.
5. El agente usa `extract_parameters`.
6. Se extraen:
   - `nombre`: Camiseta Negra Roma
   - `precio`: 19.99
   - `stock`: 25
   - `categoria`: camisetas
7. Como no faltan datos, el agente llama a `run_workflow`.
8. `runner.py` abre el formulario con Playwright.
9. Rellena los campos y pulsa Guardar.
10. Espera el texto `Guardado` en el toast.
11. Devuelve el resultado al agente.
12. El agente responde en lenguaje natural.
13. La API devuelve esa respuesta a MAUI.

### 2.4. Que es RAG aqui

En este proyecto, RAG no se usa para responder una pregunta general, sino para seleccionar procedimientos RPA.

La base vectorial guarda informacion de cada JSON:

- titulo
- descripcion
- aplicacion
- tags
- parametros

Cuando el usuario pide "dame de alta un producto", el sistema busca semanticamente que procedimiento encaja mejor. Si manana se anadieran mas workflows, por ejemplo `baja_producto` o `consulta_stock`, el agente podria elegir entre ellos.

### 2.5. Que es el workflow JSON

El workflow es una receta ejecutable. Ejemplo simplificado:

```json
{
  "type": "type",
  "target": { "by": "id", "value": "nombre" },
  "value": "{{nombre}}"
}
```

Esto significa:

- busca el elemento HTML con `id="nombre"`;
- escribe el valor del parametro `nombre`;
- el valor real se recibe desde el texto del usuario.

## 3. Proyecto MAUI: `maui_app`

Este proyecto es la interfaz visual. Es una app .NET MAUI Blazor Hybrid: usa MAUI como contenedor nativo y Blazor/Razor para la UI.

### 3.1. Archivos principales

`RPAChat.App/RPAChat.App.csproj`

- Configura la app MAUI.
- Target frameworks:
  - Android
  - iOS
  - MacCatalyst
  - Windows
- Activa `UseMaui`.
- Usa Blazor WebView con `Microsoft.AspNetCore.Components.WebView.Maui`.

`RPAChat.App/MauiProgram.cs`

- Configura los servicios de la app.
- Registra `BlazorWebView`.
- Registra un `HttpClient` con:

```csharp
BaseAddress = new Uri("http://127.0.0.1:8000")
```

- Registra `RpaAgentClient`, que sera usado por la pagina del chat.

`RPAChat.App/Services/RpaAgentClient.cs`

- Es el cliente C# que llama al backend.
- Define los modelos:
  - `ChatRequest`
  - `ChatResponse`
- Envia `POST /chat` con:
  - `message`
  - `session_id`
- Maneja errores HTTP y respuestas vacias.

`RPAChat.App/Components/Pages/Home.razor`

- Es la pantalla principal.
- Muestra:
  - titulo de la app
  - estado del agente
  - sesion activa
  - API y formulario
  - ventana de mensajes
  - textarea para escribir
  - acciones rapidas
  - tarjetas explicando capacidades
- Cuando se pulsa Enviar:
  1. Guarda el texto del usuario.
  2. Limpia el input.
  3. Pone el estado en `Procesando agente`.
  4. Llama a `AgentClient.SendAsync`.
  5. Muestra la respuesta o el error.

`RPAChat.App/wwwroot/index.html`

- Es el HTML base de Blazor WebView.
- Carga CSS.
- Define `window.rpaChat.scrollToLatest`, funcion JavaScript para hacer scroll automatico al ultimo mensaje.

`RPAChat.App/wwwroot/css/app.css`

- Contiene el estilo visual de la app.
- Tema oscuro moderno.
- Panel principal estilo consola.
- Burbujas de chat.
- Chips de acciones rapidas.
- Responsive para movil.

`RPAChat.App/Components/Layout/MainLayout.razor`

- Layout principal de la app.
- Envuelve la pagina en `<main class="app-stage">`.

### 3.2. Flujo dentro de MAUI

1. El usuario escribe en el textarea.
2. `SendMessageAsync` valida que haya texto.
3. Se anade un mensaje del usuario a la lista `Messages`.
4. Se llama a:

```csharp
AgentClient.SendAsync(userPrompt, _sessionId)
```

5. `RpaAgentClient` envia la peticion HTTP al backend.
6. Si `ok=true`, se muestra `result.Response`.
7. Si `ok=false`, se muestra `result.Error`.
8. El chat hace scroll al ultimo mensaje.

### 3.3. Por que existe `session_id`

El `session_id` sirve para mantener continuidad de conversacion en el agente. En `agent.py` se usa `MemorySaver`, y en `api.py` se pasa:

```python
config = {"configurable": {"thread_id": session_id}}
```

Asi el agente puede asociar varios mensajes a una misma sesion.

## 4. Como arrancar el sistema

Usa terminales separadas para cada componente:

### Terminal 1: LM Studio

1. Abrir LM Studio.
2. Cargar un modelo de chat compatible con tool calling.
3. Activar servidor OpenAI-compatible.
4. Debe quedar en:

```text
http://localhost:1234/v1
```

Comprobacion opcional:

```powershell
Invoke-WebRequest http://localhost:1234/v1/models
```

### Terminal 2: formulario web

```powershell
cd rpa_agent_project
.\venv\Scripts\activate
python web_form\server.py
```

Abrir:

```text
http://localhost:8081
```

### Terminal 3: indexar RAG

Solo hace falta cuando no existe `rag/chroma_db` o si cambias los JSON:

```powershell
cd rpa_agent_project
.\venv\Scripts\activate
python rag\index_procedures.py
```

### Terminal 4: API Python

```powershell
cd rpa_agent_project
.\venv\Scripts\activate
python api.py
```

Comprobar:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

### Terminal 5: MAUI

```powershell
cd maui_app
dotnet build .\RPAChat.App\RPAChat.App.csproj -t:Run -f net9.0-windows10.0.19041.0
```

## 5. Errores tipicos y diagnostico

### La API no responde

Comprobar:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

Si falla, abrir `python api.py`.

### El agente no llama a tools

Posible causa:

- El modelo de LM Studio no soporta tool calling.
- No esta activo el servidor OpenAI-compatible.

### RAG no encuentra procedimientos

Comprobar que existe:

```text
rpa_agent_project/rag/chroma_db
```

Si no existe:

```powershell
python rag\index_procedures.py
```

### Playwright no abre navegador

Ejecutar:

```powershell
python -m playwright install chromium
```

### El formulario no carga

Comprobar:

```text
http://localhost:8081
```

Si no carga, ejecutar:

```powershell
python web_form\server.py
```

### MAUI no conecta con la API

Revisar en `MauiProgram.cs`:

```csharp
BaseAddress = new Uri("http://127.0.0.1:8000")
```

Y confirmar que `api.py` esta levantada en ese puerto.

## 6. Resumen de conceptos clave

**RAG para selección de procedimientos**

La base vectorial no responde preguntas genéricas, sino que selecciona qué procedimiento RPA ejecutar. Cuando el usuario dice "dame de alta un producto", ChromaDB busca semanticamente cuál procedimiento (JSON) encaja mejor.

**Workflows desacoplados del agente**

Los procedimientos están documentados en JSON, indexados en ChromaDB y recuperados dinámicamente. Esto permite añadir nuevos procesos sin reescribir el agente ni el prompt.

**Validación de parámetros obligatorios**

El `SYSTEM_PROMPT` instruye al agente para no ejecutar el RPA hasta tener todos los parámetros requeridos. Si faltan datos, pregunta al usuario antes de proceder.

**Separación de responsabilidades**

- **MAUI**: Interfaz de chat y visualización
- **FastAPI**: Puente HTTP entre MAUI y el agente
- **LangChain**: Razonamiento y orquestación mediante tools
- **ChromaDB**: Memoria de procedimientos disponibles
- **Playwright**: Motor que ejecuta pasos reales en el navegador
- **LM Studio**: Modelo local compatible con OpenAI API para tool calling

