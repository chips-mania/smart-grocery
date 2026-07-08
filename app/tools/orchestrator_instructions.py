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

When answering from plan_one_meal JSON, show ALL sections in this order (do not summarize away shopping details):
1) meal_tray — 국/메인/반찬 레시피명
2) menu_ingredients — 각 요리별 재료와 amount+unit (또는 count)
3) from_fridge — 냉장고 재료로 쓰는 항목
4) assumed_at_home — 집에 있다고 가정한 양념/재료 (buy_list에 없음)
5) buy_list — 구매 필요 재료와 required_amount+required_unit
6) shopping_selections — 재료별 Kurly 상품명, quantity, line_price, leftover_amount+leftover_unit
7) total_price, leftover_score, leftover_summary

Cite only numbers from tool JSON. Basic pantry (간장, 굴소스, etc.) is assumed at home unless user says missing.
"""

AI_REVIEW = {
    "search_recipes": (
        "Browse-only. If user wants a full meal or shopping list, call plan_one_meal instead."
    ),
    "plan_one_meal": (
        "한국어로 응답. meal_tray → menu_ingredients(양 포함) → from_fridge → assumed_at_home → "
        "buy_list → shopping_selections(상품명·수량·가격·잔량) → total_price·leftover_score 순으로 모두 표시. "
        "Pantry는 assumed_at_home만. 돼지고기 냉장고인데 소고기/갈비탕이면 query에 돼지고기 명시 후 재호출."
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
