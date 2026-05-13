from __future__ import annotations

from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BASE_DIR / ".env"


def _load_env_fallback(path: Path, *, override: bool) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if override or key not in os.environ:
            os.environ[key] = value


def load_environment(*, override: bool = False) -> Path:
    """Load project-level .env values without replacing existing shell vars."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_env_fallback(ENV_PATH, override=override)
    else:
        load_dotenv(dotenv_path=ENV_PATH, override=override)

    return ENV_PATH
