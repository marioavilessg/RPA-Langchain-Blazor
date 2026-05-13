from __future__ import annotations

import json
import warnings
from pathlib import Path

from langchain_core._api.deprecation import LangChainDeprecationWarning
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma


warnings.filterwarnings("ignore", category=LangChainDeprecationWarning)

BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "rag" / "chroma_db"


embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
db = Chroma(persist_directory=str(DB_PATH), embedding_function=embeddings)

results = db.similarity_search_with_score("alta producto camiseta", k=1)

print("RESULTADOS:", len(results))

for doc, distance in results:
    metadata = dict(doc.metadata)
    if "param_schema" in metadata:
        metadata["param_schema"] = json.loads(metadata["param_schema"])

    score = round(1 / (1 + float(distance)), 4)
    print("\nCONTENIDO:")
    print(doc.page_content)
    print("\nMETADATA:")
    print(json.dumps(metadata, indent=2, ensure_ascii=True))
    print("\nSCORE:", score)
