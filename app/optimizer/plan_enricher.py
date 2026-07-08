def _alternative_summary(plan: dict) -> dict:

    return {
        "meals": [
            {"day": meal["day"], "recipe_name": meal["recipe_name"]}
            for meal in plan.get("meals", [])
        ],
        "cost": plan.get("cost", {}),
        "menu_names": [meal["recipe_name"] for meal in plan.get("meals", [])],
    }


def enrich_plan(
    plan: dict,
    *,
    budget: int | None,
    duration_days: int,
    people: int,
    meals_per_day: int = 1,
    preference: str = "minimize_waste",
    expensive_menu: str | None = None,
    alternative_plan: dict | None = None,
) -> dict:

    total = plan["cost"]["total"]
    within_budget = plan["cost"]["within_budget"]
    gap = max(total - budget, 0) if budget is not None else 0
    plan["cost"]["budget_gap"] = gap

    suggestions: list[str] = []
    next_actions: list[dict] = []
    menu_names = [meal["recipe_name"] for meal in plan.get("meals", [])]

    if budget is None:
        plan["suggestions"] = suggestions
        plan["next_actions"] = next_actions
        return plan

    if within_budget:
        if plan.get("leftovers"):
            suggestions.append(
                "남는 재료가 있습니다. replace_menu로 대체 메뉴를 검토해 보세요."
            )
            next_actions.append(
                {
                    "tool": "replace_menu",
                    "args_hint": {"current_menus": menu_names},
                }
            )
        plan["suggestions"] = suggestions
        plan["next_actions"] = next_actions
        return plan

    suggestions.append(
        f"현재 조합은 예산을 {gap:,}원 초과합니다. "
        f"아래 장보기 목록은 참고용입니다."
    )

    if expensive_menu:
        suggestions.append(
            f"'{expensive_menu}' 메뉴를 replace_menu로 바꾸면 비용을 줄일 수 있습니다."
        )
        next_actions.append(
            {
                "tool": "replace_menu",
                "args_hint": {
                    "current_menus": menu_names,
                    "menu_to_replace": expensive_menu,
                },
            }
        )

    if alternative_plan and alternative_plan["cost"]["within_budget"]:
        plan["alternatives"] = {
            "budget_friendly": _alternative_summary(alternative_plan),
        }
        alt_total = alternative_plan["cost"]["total"]
        suggestions.append(
            f"인원·일수는 그대로 두고, 예산({budget:,}원)에 맞는 대안 조합을 찾았습니다 "
            f"(약 {alt_total:,}원). alternatives.budget_friendly를 참고하세요."
        )
    elif alternative_plan is not None:
        alt_gap = max(alternative_plan["cost"]["total"] - budget, 0)
        if alt_gap < gap:
            plan["alternatives"] = {
                "budget_friendly": _alternative_summary(alternative_plan),
            }
            suggestions.append(
                f"더 저렴한 메뉴 조합을 찾았지만 예산을 {alt_gap:,}원 초과합니다. "
                f"replace_menu로 메뉴를 바꿔 보세요."
            )
        else:
            suggestions.append(
                "현재 예산·인원·일수 조건으로는 비용을 맞추기 어렵습니다. "
                "replace_menu로 메뉴를 바꿔 보세요."
            )
    elif preference != "minimize_cost":
        suggestions.append(
            "인원·일수는 그대로 두고, preference=minimize_cost로 더 저렴한 메뉴 조합을 "
            "다시 추천받아 보세요."
        )
        next_actions.append(
            {
                "tool": "optimize_meal_plan",
                "args_hint": {
                    "budget": budget,
                    "people": people,
                    "duration_days": duration_days,
                    "meals_per_day": meals_per_day,
                    "preference": "minimize_cost",
                },
            }
        )
    else:
        suggestions.append(
            "현재 예산·인원·일수 조건으로는 비용을 맞추기 어렵습니다. "
            "replace_menu로 메뉴를 바꿔 보세요."
        )

    plan["suggestions"] = suggestions
    plan["next_actions"] = next_actions
    return plan
