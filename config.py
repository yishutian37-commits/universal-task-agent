import os
from pathlib import Path


def load_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:15721/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "glm-5.2")
NO_PROXY = os.getenv("NO_PROXY", "127.0.0.1,localhost")
TAM_ENABLE = os.getenv("TAM_ENABLE", "0") == "1"
TAM_DB_PATH = os.getenv("TAM_DB_PATH", "memory/tam-memory.db")
