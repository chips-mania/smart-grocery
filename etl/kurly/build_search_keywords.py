import json
from collections import defaultdict
from pathlib import Path

from etl.common.logger import error, info, success
from etl.kurly.ingredient_keyword_map import INGREDIENT_KEYWORDS

CONTEXT_FILE = Path("data/processed/kurly/ingredient_context.json")
OUTPUT_FILE = Path("data/processed/kurly/search_keywords.json")


def build_search_keywords() -> list[dict]:
    keyword_to_ingredients: dict[str, set[str]] = defaultdict(set)

    for ingredient, keywords in INGREDIENT_KEYWORDS.items():
        for keyword in keywords:
            keyword_to_ingredients[keyword].add(ingredient)

    result = [
        {
            "search_keyword": keyword,
            "ingredients": sorted(ingredients),
        }
        for keyword, ingredients in sorted(keyword_to_ingredients.items())
    ]
    return result


def validate(context: list[dict], search_keywords: list[dict]) -> bool:
    context_ingredients = [item["ingredient"] for item in context]
    context_set = set(context_ingredients)

    mapped_ingredients = set(INGREDIENT_KEYWORDS.keys())
    covered: set[str] = set()
    ingredient_occurrences: dict[str, int] = defaultdict(int)

    for entry in search_keywords:
        for ingredient in entry["ingredients"]:
            covered.add(ingredient)
            ingredient_occurrences[ingredient] += 1

    missing_from_map = sorted(context_set - mapped_ingredients)
    extra_in_map = sorted(mapped_ingredients - context_set)
    uncovered = sorted(context_set - covered)
    duplicates = {
        ingredient: count
        for ingredient, count in sorted(ingredient_occurrences.items())
        if count > 1
    }

    info("=" * 50)
    info("검증 결과")
    info("=" * 50)
    info(f"1. ingredient_context.json ingredient 개수: {len(context_set)}")
    info(f"2. search_keywords.json에 포함된 ingredient 개수: {len(covered)}")
    info(f"3. 매핑 딕셔너리 ingredient 개수: {len(mapped_ingredients)}")

    if missing_from_map:
        error(f"매핑 누락 ({len(missing_from_map)}개):")
        for item in missing_from_map:
            error(f"  - {item}")

    if extra_in_map:
        error(f"매핑에만 존재 ({len(extra_in_map)}개):")
        for item in extra_in_map:
            error(f"  - {item}")

    if uncovered:
        error(f"search_keyword 미포함 ingredient ({len(uncovered)}개):")
        for item in uncovered:
            error(f"  - {item}")
    else:
        success("모든 ingredient가 최소 1개 search_keyword에 포함됨")

    if duplicates:
        info(f"4. 복수 search_keyword 포함 ingredient ({len(duplicates)}개, 허용):")
        for ingredient, count in duplicates.items():
            keywords = [
                entry["search_keyword"]
                for entry in search_keywords
                if ingredient in entry["ingredients"]
            ]
            info(f"  - {ingredient} ({count}개): {', '.join(keywords)}")
    else:
        info("4. 복수 search_keyword 포함 ingredient: 없음")

    # search_keyword 중복 검사
    keyword_names = [entry["search_keyword"] for entry in search_keywords]
    dup_keywords = [k for k in keyword_names if keyword_names.count(k) > 1]
    if dup_keywords:
        error(f"5. 중복 search_keyword: {set(dup_keywords)}")
    else:
        success(f"5. search_keyword 중복 없음 (총 {len(keyword_names)}개)")

    ok = not missing_from_map and not uncovered and not dup_keywords
    info("=" * 50)
    if ok:
        success("검증 통과")
    else:
        error("검증 실패 — 위 항목을 확인하세요")
    return ok


def main():
    info("Loading ingredient context...")
    with open(CONTEXT_FILE, encoding="utf-8") as f:
        context = json.load(f)

    info("Building search keywords...")
    search_keywords = build_search_keywords()

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(search_keywords, f, ensure_ascii=False, indent=2)

    success(f"Saved {len(search_keywords)} search keywords → {OUTPUT_FILE}")

    validate(context, search_keywords)


if __name__ == "__main__":
    main()
