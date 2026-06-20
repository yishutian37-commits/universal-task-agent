import os

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:15721/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "glm-5.2")
NO_PROXY = os.getenv("NO_PROXY", "127.0.0.1,localhost")
TAM_ENABLE = os.getenv("TAM_ENABLE", "0") == "1"
TAM_DB_PATH = os.getenv("TAM_DB_PATH", "memory/tam-memory.db")
