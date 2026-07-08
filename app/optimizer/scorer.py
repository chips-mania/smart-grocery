from app.optimizer.preferences import get_weights


def score_plan(
    plan: dict,
    preference: str | None = None,
    preferred_menus: list[str] | None = None,
) -> dict:
    weights = get_weights(preference)
    budget = plan["meta"].get("budget") or 0
    total = plan["cost"]["total"]

    cost_score = 0.0
    if budget > 0:
        cost_score = max(0.0, (1 - total / budget)) * 100 * weights["cost"]

    waste_penalty = 0.0
    for item in plan.get("leftovers", []):
        if item.get("leftover_confidence") == "unknown":
            waste_penalty += 30
        elif item.get("amount"):
            waste_penalty += min(item["amount"] / 100, 30)

    waste_score = max(0.0, 100 - waste_penalty) * weights["waste"]

    discount_bonus = 0.0
    discount_savings = plan["cost"].get("discount_savings") or 0
    if discount_savings > 0:
        discount_bonus = min(discount_savings / 1000, 1.0) * 100 * weights["discount"]

    sharing_bonus = 0.0
    shared = plan.get("highlights", {}).get("shared_ingredients") or []
    sharing_bonus = min(len(shared) * 10, 50) * weights["sharing"] * 2

    nutrition_match = 0.0
    if preference == "high_protein":
        protein_sum = sum(
            meal.get("protein_g") or meal.get("protein") or 0
            for meal in plan.get("meals", [])
        )
        nutrition_match = min(protein_sum / 50, 1.0) * 100 * weights["nutrition"]
    elif preference == "low_calorie":
        kcal_sum = sum(
            float(meal.get("kcal") or 0)
            for meal in plan.get("meals", [])
        )
        meal_count = len(plan.get("meals", [])) or 1
        target_weekly = 350 * meal_count
        nutrition_match = max(0.0, (target_weekly - kcal_sum) / target_weekly)
        nutrition_match = min(nutrition_match, 1.0) * 100 * weights["nutrition"]

    preference_match = 0.0
    if preferred_menus:
        selected_names = {meal["recipe_name"] for meal in plan.get("meals", [])}
        matched = len(selected_names.intersection(set(preferred_menus)))
        preference_match = (matched / len(preferred_menus)) * 100 * 0.1

    diversity_bonus = 0.0
    unique_recipes = len(
        {meal["recipe_id"] for meal in plan.get("meals", []) if meal.get("recipe_id")}
    )
    if unique_recipes == len(plan.get("meals", [])):
        diversity_bonus = 20 * weights["diversity"] * 5

    fridge_savings = plan.get("highlights", {}).get("fridge_savings") or 0
    fridge_bonus = min(fridge_savings / 5000, 1.0) * 20

    total_score = (
        cost_score
        + waste_score
        + discount_bonus
        + sharing_bonus
        + nutrition_match
        + preference_match
        + diversity_bonus
        + fridge_bonus
    )

    return {
        "score": round(min(total_score, 100), 1),
        "score_breakdown": {
            "cost_score": round(cost_score, 1),
            "waste_penalty": round(-waste_penalty * weights["waste"], 1),
            "discount_bonus": round(discount_bonus, 1),
            "ingredient_sharing": round(sharing_bonus, 1),
            "nutrition_match": round(nutrition_match, 1),
            "preference_match": round(preference_match, 1),
            "diversity_bonus": round(diversity_bonus, 1),
            "fridge_bonus": round(fridge_bonus, 1),
        },
    }


def build_reasons(plan: dict) -> list[str]:
    reasons: list[str] = []

    shared = plan.get("highlights", {}).get("shared_ingredients") or []
    if shared:
        joined = "·".join(shared[:5])
        reasons.append(
            f"{joined}을(를) 여러 메뉴에서 공유해 잔여 재료를 줄였습니다"
        )

    discount_savings = plan["cost"].get("discount_savings") or 0
    if discount_savings > 0:
        reasons.append(
            f"할인 상품을 반영해 약 {discount_savings:,}원 절약했습니다"
        )

    fridge_savings = plan.get("highlights", {}).get("fridge_savings") or 0
    if fridge_savings > 0:
        reasons.append(
            f"냉장고 보유 재료를 우선 사용해 약 {fridge_savings:,}원 절약했습니다"
        )

    assumptions = plan.get("assumptions") or {}
    pantry_used = assumptions.get("pantry_ingredients_used") or []
    if pantry_used:
        joined = "·".join(pantry_used[:5])
        reasons.append(
            f"기본 양념·조미료({joined} 등)는 집에 있다고 가정해 장보기에서 제외했습니다"
        )

    nutrition = plan.get("nutrition_summary") or {}
    if nutrition.get("total_protein_g") or nutrition.get("total_kcal"):
        density_note = ""
        if nutrition.get("avg_protein_density"):
            density_note = (
                f", 100kcal당 평균 단백질 {nutrition.get('avg_protein_density')}g"
            )
        reasons.append(
            f"총 단백질 약 {nutrition.get('total_protein_g', 0):g}g, "
            f"총 칼로리 약 {nutrition.get('total_kcal', 0):g}kcal "
            f"(끼니당 평균 단백질 {nutrition.get('daily_avg_protein_g', 0):g}g, "
            f"칼로리 {nutrition.get('daily_avg_kcal', 0):g}kcal{density_note})입니다"
        )
    adjusted = nutrition.get("adjusted_meal_count") or 0
    if adjusted:
        reasons.append(
            f"원본 영양 DB 오류가 의심되는 메뉴 {adjusted}개는 "
            f"칼로리·탄수화물·지방 기준으로 단백질을 보정해 계산했습니다"
        )

    shopping_items = [
        row for row in plan.get("ingredient_ledger", []) if row.get("source") == "shopping"
    ]
    if shopping_items:
        sample = shopping_items[0]
        if sample.get("leftover_amount") is not None:
            reasons.append(
                f"예: {sample['ingredient']} {sample.get('used_amount')}"
                f"{sample.get('used_unit') or ''} 사용, "
                f"구매 후 약 {sample['leftover_amount']}"
                f"{sample.get('leftover_unit') or ''} 남음"
            )

    if plan["cost"].get("within_budget"):
        budget = plan["meta"].get("budget")
        if budget:
            reasons.append(
                f"총 장보기 비용 {plan['cost']['total']:,}원으로 예산 "
                f"{budget:,}원 이내입니다"
            )
    elif plan["meta"].get("budget"):
        budget = plan["meta"]["budget"]
        reasons.append(
            f"예산 {budget:,}원을 "
            f"{plan['cost']['total'] - budget:,}원 초과했습니다"
        )

    return reasons


def build_highlights(plan: dict) -> dict:
    return {
        "shared_ingredients": plan.get("highlights", {}).get("shared_ingredients") or [],
        "discount_savings": plan["cost"].get("discount_savings") or 0,
        "fridge_savings": plan.get("highlights", {}).get("fridge_savings") or 0,
        "budget_remaining": plan["cost"].get("budget_remaining") or 0,
        "nutrition_summary": plan.get("nutrition_summary") or {},
    }
