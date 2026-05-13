from pathlib import Path
import sys


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.runner import run_workflow


params = {
    "nombre": "Camiseta Negra Roma",
    "precio": 19.99,
    "stock": 25,
    "categoria": "camisetas",
}

result = run_workflow("alta_producto", params, headless=True)

print(result)
