import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import TCPServer


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from shared.config import load_environment


load_environment()

PORT = int(os.getenv("WEB_FORM_PORT", "8081"))
WEB_DIR = Path(__file__).resolve().parent


class ReusableTCPServer(TCPServer):
    allow_reuse_address = True


Handler = partial(SimpleHTTPRequestHandler, directory=str(WEB_DIR))

with ReusableTCPServer(("", PORT), Handler) as httpd:
    print(f"Servidor corriendo en http://localhost:{PORT}")
    print(f"Sirviendo archivos desde {WEB_DIR}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido correctamente.")
