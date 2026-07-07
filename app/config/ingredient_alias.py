import json
from pathlib import Path

ALIAS_PATH = Path("data/aliases/ingredient_aliases.json")

with open(ALIAS_PATH, encoding="utf-8") as f:
    INGREDIENT_ALIASES = json.load(f)