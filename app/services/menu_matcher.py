def score_menu_match(query: str, recipe_name: str) -> float:

    q = query.strip().lower()
    n = recipe_name.strip().lower()

    if not q or not n:
        return 0.0

    if q == n:
        return 1.0
    if n.endswith(q):
        return 0.9 - len(n) * 0.001
    if n.startswith(q):
        return 0.85 - len(n) * 0.001
    if q in n:
        return 0.7 - len(n) * 0.001

    return 0.0


MIN_MATCH_SCORE = 0.5


def build_resolution_entry(
    *,
    query: str,
    recipe: dict,
    score: float,
    alternatives: list[str],
) -> dict:

    return {
        "input": query,
        "resolved": recipe["name"],
        "score": round(score, 2),
        "auto_selected": score < 1.0,
        "alternatives": alternatives,
        "recipe": recipe,
    }


def apply_menu_resolution(plan: dict, resolutions: list[dict]) -> dict:

    public_resolutions = [
        {
            "input": row["input"],
            "resolved": row["resolved"],
            "score": row["score"],
            "auto_selected": row["auto_selected"],
            "alternatives": row["alternatives"],
        }
        for row in resolutions
    ]
    plan["menu_resolution"] = public_resolutions

    auto_selected = [row for row in public_resolutions if row["auto_selected"]]
    if not auto_selected:
        return plan

    summary = ", ".join(
        f"'{row['input']}'→'{row['resolved']}'" for row in auto_selected[:3]
    )
    note = (
        f"{summary} 메뉴는 검색 결과 중 유사도가 가장 높은 레시피로 선택했습니다. "
        "원하시는 메뉴가 다르면 말씀해 주시면 반영할 수 있습니다."
    )

    plan["user_choice_available"] = True
    plan["user_choice_note"] = note
    plan["reasons"] = [note, *plan.get("reasons", [])]

    return plan
