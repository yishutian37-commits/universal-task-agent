from __future__ import annotations

import os
from datetime import datetime

from rag.errors import IngestError
from rag.loaders.base import LoadedDoc


def _detect_type(source: str) -> str:
    return os.path.splitext(source)[1].lstrip(".").lower() or "txt"


class TextLoader:
    """读取纯文本文件（.md / .txt）为 LoadedDoc。"""

    def load(self, source: str) -> LoadedDoc:
        try:
            text = open(source, encoding="utf-8").read()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise IngestError(f"读取文件失败 {source}: {exc}") from exc

        file_type = _detect_type(source)
        title = os.path.splitext(os.path.basename(source))[0]
        return LoadedDoc(
            text=text,
            source=source,
            metadata={
                "type": file_type,
                "title": title,
                "size": len(text),
                "ingested_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
