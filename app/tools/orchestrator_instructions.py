"""PlayMCP orchestrator (LLM) instructions — validate at every step."""

MCP_SERVER_INSTRUCTIONS = """\
Smart Grocery(알뜰장보기): minimize leftover after one meal (soup + main + side; no rice).

TOOLS (5):
1) plan_one_meal — DEFAULT. One call returns menu, ingredients, buy_list, Kurly picks, leftovers, price.
2) search_recipes — browse candidates or recover when plan_one_meal fails.
3) propose_meal_trays — build tray combos from search results (no Kurly calls).
4) pick_best_meal_tray — Kurly simulation on trays; picks lowest leftover_score.
5) kurly_search — single-ingredient Kurly browse only.

CRITICAL: Each tray slot MUST be a real recipe — soup=국&찌개, main=일품, side=반찬.

Default flow: plan_one_meal with fridge_items.
Fallback (only if plan_one_meal fails): search_recipes → propose_meal_trays → pick_best_meal_tray.
Do NOT chain many tools when plan_one_meal can answer in one call.

When answering from plan_one_meal or pick_best_meal_tray JSON, show: meal_tray, menu_ingredients \
(with amounts), from_fridge, assumed_at_home, buy_list, shopping_selections (product, price, leftover), \
total_price, leftover_score. Cite only numbers from tool JSON.
"""

AI_REVIEW = {
    "search_recipes": (
        "Review candidates: name matches intent, category fits slot. "
        "If user wanted full meal, prefer plan_one_meal next time."
    ),
    "propose_meal_trays": (
        "Review trays: soup/main/side are real recipes with correct categories. "
        "Then call pick_best_meal_tray once — do not manually kurly_search each ingredient."
    ),
    "pick_best_meal_tray": (
        "Present winner meal_tray, buy_list, shopping_selections, total_price, leftover_score. "
        "If weak, re-run plan_one_meal with different query or soup_recipe_id."
    ),
    "plan_one_meal": (
        "Present full JSON sections in Korean. If menu mismatches intent, re-run with query "
        "or soup_recipe_id — do not fall back to long manual tool chains."
    ),
    "kurly_search": (
        "Show product name and price. For full meal use plan_one_meal instead."
    ),
}


def with_ai_review(step: str, payload: dict) -> dict:
    """Attach orchestrator validation hint to a tool response."""
    review = AI_REVIEW.get(step)
    if review:
        payload = dict(payload)
        payload["ai_review"] = review
    return payload
