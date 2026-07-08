"""PlayMCP orchestrator (LLM) instructions — validate at every step."""

MCP_SERVER_INSTRUCTIONS = """\
Smart Grocery(알뜰장보기): minimize leftover ingredients after one meal \
(soup + main + side; no rice).

TOOLS (only 3 — use the right one):
1) plan_one_meal — DEFAULT for fridge leftovers, menu requests, shopping optimization. \
One call returns menu, per-recipe ingredients, buy_list, Kurly picks, leftovers, total price.
2) search_recipes — ONLY when user wants recipe candidates without shopping (browse/explore).
3) kurly_search — ONLY when user asks to search Kurly for one ingredient/product keyword.

For "냉장고에 X 남았어 뭐 해먹지?" or "된장찌개 장보기 최적화" → plan_one_meal (NOT search_recipes alone).

When answering from plan_one_meal JSON, show in order:
1) meal_tray (soup/main/side recipe names)
2) menu_ingredients (each dish + required amounts)
3) from_fridge + assumed_at_home (pantry staples like 굴소스 excluded from buy)
4) buy_list (what to purchase + required amounts)
5) shopping_selections (Kurly product, price, leftover per item)
6) total_price + leftover_score

Cite only numbers from tool JSON. Basic pantry (간장, 굴소스, etc.) is assumed at home unless user says missing.
"""

AI_REVIEW = {
    "search_recipes": (
        "Browse-only. If user wants a full meal or shopping list, call plan_one_meal instead."
    ),
    "plan_one_meal": (
        "Present meal_tray, menu_ingredients, buy_list, shopping_selections, total_price, "
        "leftover_score. Pantry items are in assumed_at_home, not buy_list. "
        "Re-run with different query if menu mismatches user intent (e.g. 꽃게된장 vs 된장찌개)."
    ),
    "kurly_search": (
        "Show product name, effective_price/discount_price. Filter irrelevant hits. "
        "For full meal planning use plan_one_meal instead."
    ),
}


def with_ai_review(step: str, payload: dict) -> dict:
    """Attach orchestrator validation hint to a tool response."""
    review = AI_REVIEW.get(step)
    if review:
        payload = dict(payload)
        payload["ai_review"] = review
    return payload
