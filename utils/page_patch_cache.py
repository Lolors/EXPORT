from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from types import CodeType


@lru_cache(maxsize=16)
def read_text_cached(path_text: str, modified_ns: int) -> str:
    """Read a patch source once per file version."""
    del modified_ns
    return Path(path_text).read_text(encoding='utf-8')


@lru_cache(maxsize=16)
def compile_cached(source: str, source_path: str, cache_version: str) -> CodeType:
    """Reuse compiled patched page code across Streamlit reruns."""
    del cache_version
    return compile(source, source_path, 'exec')
