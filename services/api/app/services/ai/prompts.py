from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"


@lru_cache
def load_prompt(name: str, version: str = "v1") -> str:
    path = PROMPTS_DIR / f"{name}.{version}.md"
    return path.read_text(encoding="utf-8")
