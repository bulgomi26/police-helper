import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@lru_cache(maxsize=None)
def load(name):
    """data/<name>.json 을 읽어 반환 (한 번 읽으면 캐시)."""
    with open(DATA_DIR / f"{name}.json", encoding="utf-8") as f:
        return json.load(f)
