import json
import re
from collections import Counter
from pathlib import Path

INPUT = Path("data/raw/recipes_raw.json")
OUTPUT_DIR = Path("data/analysis")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SECTION_COUNTER = Counter()
UNIT_COUNTER = Counter()
PATTERN_COUNTER = Counter()

# 현재 예상되는 section
KNOWN_SECTIONS = {
    "양념",
    "양념장",
    "고명",
    "소스",
    "드레싱",
    "육수",
    "채소준비",
    "반죽",
    "토핑",
}

# 단위
UNIT_PATTERN = re.compile(
    r"(kg|g|mg|ml|L|개|모|대|줄기|알|마리|컵|큰술|작은술|봉|팩|장|줌)"
)

with open(INPUT, encoding="utf-8") as f:
    recipes = json.load(f)

for recipe in recipes:

    parts = recipe.get("RCP_PARTS_DTLS", "")

    if not parts:
        continue

    for line in parts.splitlines():

        line = line.strip()

        if not line:
            continue

        # section 분석
        if line in KNOWN_SECTIONS:
            SECTION_COUNTER[line] += 1
            continue

        # 단위 분석
        units = UNIT_PATTERN.findall(line)

        for u in units:
            UNIT_COUNTER[u] += 1

        # 패턴 저장
        PATTERN_COUNTER[line] += 1

# 저장

with open(OUTPUT_DIR / "sections.json", "w", encoding="utf-8") as f:
    json.dump(
        SECTION_COUNTER.most_common(),
        f,
        ensure_ascii=False,
        indent=2,
    )

with open(OUTPUT_DIR / "units.json", "w", encoding="utf-8") as f:
    json.dump(
        UNIT_COUNTER.most_common(),
        f,
        ensure_ascii=False,
        indent=2,
    )

with open(OUTPUT_DIR / "ingredient_patterns.json", "w", encoding="utf-8") as f:
    json.dump(
        PATTERN_COUNTER.most_common(300),
        f,
        ensure_ascii=False,
        indent=2,
    )

print("=" * 50)
print("Recipe Analysis Complete")
print("=" * 50)

print(f"Sections : {len(SECTION_COUNTER)}")
print(f"Units    : {len(UNIT_COUNTER)}")
print(f"Patterns : {len(PATTERN_COUNTER)}")

print("=" * 50)