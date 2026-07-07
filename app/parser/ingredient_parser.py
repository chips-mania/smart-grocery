import re

from app.config.ingredient_alias import INGREDIENT_ALIASES
from app.models.ingredient import Ingredient

GRAM_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(g|kg|ml|L)")
COUNT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(개|모|대|줄기|알|컵|봉|팩)")
FRACTION_PATTERN = re.compile(
    r"\((\d+)\/(\d+)(개|모|대|줄기|알|컵|봉|팩)\)"
)