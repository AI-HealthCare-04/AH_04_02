import json
from pathlib import Path

from rag_prototype.schemas import LifestyleGuideline

DEFAULT_LIFESTYLE_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "lifestyle_guidelines.json"


def load_lifestyle_guidelines(path: Path | None = None) -> list[LifestyleGuideline]:
    """`data/lifestyle_guidelines.json`의 만성질환 생활지침 데이터를 읽어옵니다."""
    path = path or DEFAULT_LIFESTYLE_DATA_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [LifestyleGuideline.model_validate(item) for item in raw]
