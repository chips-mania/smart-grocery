import json
import re
from pathlib import Path

INPUT = Path("data/raw/recipes_raw.json")

OUTPUT_RECIPE = Path("data/processed/recipe/recipes.json")
OUTPUT_INGREDIENT = Path("data/processed/recipe/recipe_ingredients.json")
OUTPUT_SKIPPED = Path("data/processed/logs/skipped_recipes.json")

AMOUNT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(kg|g|ml|L)")
PAREN_PATTERN = re.compile(r"\(([^()]*)\)")
STANDALONE_COUNT_PATTERN = re.compile(
    r"(\d+(?:/\d+)?|[0-9]+[½⅓⅔⅕⅛]?|½|⅓|⅔|¼|¾|1½|1⅓)\s*"
    r"(개|모|대|줄기|알|마리|장|큰술|작은술|컵|봉|팩|쪽|뿌리|송이|봉지|가닥)"
)

SECTION_PREFIXES = [
    "●주재료", "●필수재료", "●필수 재료", "●양념장", "●양념", "●소스", "●육수", "●장식",
    "•주재료", "•필수재료", "•필수 재료", "•양념장", "•양념", "•소스", "•육수", "•장식",
    "- 주재료", "- 양념장", "- 양념", "- 소스", "- 육수", "- 곁들임채소",
    "주재료", "필수재료", "필수 재료", "재료", "양념장", "양념", "소스", "육수", "드레싱",
    "장식", "고명", "토핑", "곁들이 야채", "곁들임채소", "채소준비", "완자", "대파채",
    "다시마육수", "고기완자양념", "저염간장양념", "허브오일드레싱", "복분자소스",
]

SECTION_ONLY = set(SECTION_PREFIXES)


def to_number(value: str) -> float:
    value = value.strip()
    return float(value)


def split_outside_parentheses(text: str) -> list[str]:
    result = []
    current = []
    depth = 0

    for ch in text:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth = max(depth - 1, 0)
            current.append(ch)
        elif ch == "," and depth == 0:
            token = "".join(current).strip()
            if token:
                result.append(token)
            current = []
        else:
            current.append(ch)

    token = "".join(current).strip()
    if token:
        result.append(token)

    return result


def strip_section_prefix(text: str) -> str:
    text = text.strip()
    text = text.lstrip("●•-·").strip()

    if ":" in text:
        left, right = text.split(":", 1)
        left_clean = left.strip().lstrip("●•-·").strip()
        if left_clean in SECTION_PREFIXES or any(word in left_clean for word in ["재료", "양념", "소스", "육수", "드레싱", "고명"]):
            return right.strip()

    for prefix in sorted(SECTION_PREFIXES, key=len, reverse=True):
        if text == prefix:
            return ""
        if text.startswith(prefix + " "):
            return text[len(prefix):].strip()

    return text


def extract_count(token: str) -> str | None:
    for match in PAREN_PATTERN.finditer(token):
        inner = match.group(1).strip()

        if "×" in inner or "cm" in inner:
            continue

        if re.search(r"(개|모|대|줄기|알|마리|장|큰술|작은술|컵|봉|팩|쪽|뿌리|송이|봉지|가닥)", inner):
            return inner

    m = STANDALONE_COUNT_PATTERN.search(token)
    if m:
        return f"{m.group(1)}{m.group(2)}"

    if "약간" in token:
        return "약간"

    return None


def clean_ingredient_name(token: str) -> str:
    name = token.strip()

    name = strip_section_prefix(name)

    name = re.sub(r"\[[^\]]*\]", "", name)
    name = AMOUNT_PATTERN.sub("", name)

    # 괄호 안 정보 처리
    def replace_paren(match):
        inner = match.group(1).strip()

        if not inner:
            return ""

        if "×" in inner or "cm" in inner:
            return ""

        if re.search(r"(개|모|대|줄기|알|마리|장|큰술|작은술|컵|봉|팩|쪽|뿌리|송이|봉지|가닥)", inner):
            return ""

        # 닭고기(가슴살, 120g) -> 닭고기 가슴살
        inner = AMOUNT_PATTERN.sub("", inner)
        inner = inner.replace(",", " ").strip()
        return f" {inner} " if inner else ""

    name = PAREN_PATTERN.sub(replace_paren, name)

    name = STANDALONE_COUNT_PATTERN.sub("", name)
    name = name.replace("약간", "")

    name = re.sub(r"[.:]", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = name.strip(" ,.-·●•")

    return name


def parse_ingredient(recipe_id: int, token: str) -> dict | None:
    raw = token.strip()
    token = strip_section_prefix(raw)

    if not token:
        return None

    if token in SECTION_ONLY:
        return None

    amount = None
    unit = None

    m = AMOUNT_PATTERN.search(token)
    if m:
        amount = to_number(m.group(1))
        unit = m.group(2)

        if unit == "kg":
            amount *= 1000
            unit = "g"
        elif unit == "L":
            amount *= 1000
            unit = "ml"

    count = extract_count(token)
    ingredient = clean_ingredient_name(token)

    if not ingredient:
        return None

    # 레시피명/섹션명 같은 노이즈 방지
    if amount is None and count is None:
        return None

    return {
        "recipe_id": recipe_id,
        "ingredient": ingredient,
        "amount": amount,
        "unit": unit,
        "count": count,
        "raw": raw,
    }


def is_recipe_title_line(line: str, recipe_name: str) -> bool:
    a = re.sub(r"\s+", "", line.strip())
    b = re.sub(r"\s+", "", recipe_name.strip())

    if not a:
        return False

    if a == b:
        return True

    # API 원문 첫 줄에 짧은 내부 제목이 따로 들어가는 경우 대응
    if AMOUNT_PATTERN.search(line) is None and "(" not in line and "," not in line:
        if len(a) <= 20:
            return True

    return False


def to_float_or_none(value: str):
    try:
        if value == "":
            return None
        return float(value)
    except Exception:
        return None


def main():
    with open(INPUT, encoding="utf-8") as f:
        raw_recipes = json.load(f)

    recipe_rows = []
    ingredient_rows = []
    skipped = []

    for recipe in raw_recipes:
        recipe_id = int(recipe["RCP_SEQ"])
        recipe_name = recipe.get("RCP_NM", "")

        instructions = []

        for i in range(1, 21):

            text = recipe.get(f"MANUAL{i:02}", "").strip()
            image = recipe.get(f"MANUAL_IMG{i:02}", "").strip()

            if not text:
                continue

            text = re.sub(r"^\d+\.\s*", "", text)
            text = re.sub(r"[a-zA-Z]$", "", text).strip()

            step = {
                "step": i,
                "text": text,
            }

            if image:
                step["image"] = image

            instructions.append(step)
  

        recipe_rows.append({
            "recipe_id": recipe_id,
            "name": recipe_name,
            "category": recipe.get("RCP_PAT2", ""),
            "method": recipe.get("RCP_WAY2", ""),
            "kcal": to_float_or_none(recipe.get("INFO_ENG", "")),
            "carb": to_float_or_none(recipe.get("INFO_CAR", "")),
            "protein": to_float_or_none(recipe.get("INFO_PRO", "")),
            "fat": to_float_or_none(recipe.get("INFO_FAT", "")),
            "sodium": to_float_or_none(recipe.get("INFO_NA", "")),
            "thumbnail": recipe.get("ATT_FILE_NO_MAIN", ""),
            "image": recipe.get("ATT_FILE_NO_MK", ""),
            "tip": recipe.get("RCP_NA_TIP", ""),
            "instructions": instructions,
        })

        parts = recipe.get("RCP_PARTS_DTLS", "")

        if not parts:
            skipped.append({
                "recipe_id": recipe_id,
                "name": recipe_name,
                "reason": "empty_ingredients",
            })
            continue

        count = 0

        for line in parts.splitlines():
            line = line.strip()

            if not line:
                continue

            if is_recipe_title_line(line, recipe_name):
                continue

            line = strip_section_prefix(line)

            if not line:
                continue

            tokens = split_outside_parentheses(line)

            for token in tokens:
                parsed = parse_ingredient(recipe_id, token)

                if parsed is None:
                    continue

                ingredient_rows.append(parsed)
                count += 1

        if count == 0:
            skipped.append({
                "recipe_id": recipe_id,
                "name": recipe_name,
                "reason": "no_parsed_ingredients",
            })

    OUTPUT_RECIPE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_INGREDIENT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_SKIPPED.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_RECIPE, "w", encoding="utf-8") as f:
        json.dump(recipe_rows, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_INGREDIENT, "w", encoding="utf-8") as f:
        json.dump(ingredient_rows, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_SKIPPED, "w", encoding="utf-8") as f:
        json.dump(skipped, f, ensure_ascii=False, indent=2)

    print("=" * 50)
    print("Recipe Transform Complete")
    print("=" * 50)
    print(f"Recipes      : {len(recipe_rows)}")
    print(f"Ingredients  : {len(ingredient_rows)}")
    print(f"Skipped      : {len(skipped)}")
    print("=" * 50)


if __name__ == "__main__":
    main()