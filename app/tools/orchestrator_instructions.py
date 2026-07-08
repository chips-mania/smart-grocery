"""PlayMCP orchestrator (LLM) instructions — validate at every step."""

MCP_SERVER_INSTRUCTIONS = """\
Leftover-first grocery MCP. Goal: minimize leftover ingredients after one meal \
(soup + main + side recipes; no rice). You are the orchestrator.

CRITICAL: Each tray slot MUST be a full recipe from the database — \
soup=국&찌개, main=일품, side=반찬. NEVER put ingredient names in menu slots.

AI VALIDATION AT EVERY STEP (do not skip):
1) After search_recipes — drop mismatched names/categories; keep user intent.
2) After propose_meal_trays — reject trays with missing slots or wrong categories.
3) After pick_best_meal_tray / evaluate_meal_tray — check leftover_score and failed_ingredients; \
re-search or swap recipes if results are weak.
4) After kurly_search — YOU must filter irrelevant products before select_product_min_waste.
5) Before final answer — cite only numbers from tool JSON; explain why the tray wins.

Flow: search_recipes -> propose_meal_trays -> pick_best_meal_tray \
(simulates shopping; picks lowest leftover_score). Or plan_one_meal for end-to-end. \
Per-tray: evaluate_meal_tray. Then kurly_search/filter/select if refining manually.\
"""

AI_REVIEW = {
    "search_recipes": (
        "Review each candidate: name matches user intent, category fits the slot "
        "(국&찌개/일품/반찬), not an ingredient disguised as a menu. "
        "Drop weak matches before propose_meal_trays."
    ),
    "propose_meal_trays": (
        "Review each tray: soup/main/side are all real recipe names with correct categories. "
        "Reject incomplete trays or ingredient-only slots. "
        "Prefer trays with shared ingredients and fewer purchases."
    ),
    "evaluate_meal_tray": (
        "Review leftover_score, failed_ingredients, and skipped_unparsable. "
        "If shopping failed for key items, try another tray or re-search recipes."
    ),
    "pick_best_meal_tray": (
        "Compare ranking by leftover_score (lower is better). "
        "Verify the winner is shoppable; if not, evaluate the next tray."
    ),
    "plan_one_meal": (
        "Review the returned meal_tray, leftover_score, and failed_ingredients. "
        "If unsatisfactory, re-run with a different query or soup_recipe_id."
    ),
    "aggregate_buy_list": (
        "Verify buy_list matches the selected tray recipes and subtracts fridge/pantry."
    ),
    "kurly_search": (
        "Filter irrelevant products (wrong ingredient, prepared dish, non-grocery). "
        "Only parsable-package products can be purchased. "
        "Then call select_product_min_waste with filtered candidates."
    ),
    "select_product_min_waste": (
        "Confirm the selection minimizes leftover for the required amount/count. "
        "If no_parsable_candidates, re-filter kurly_search results or adjust keyword."
    ),
    "score_leftovers": (
        "Use leftover_score to compare alternative selections; lower is better."
    ),
}


def with_ai_review(step: str, payload: dict) -> dict:
    """Attach orchestrator validation hint to a tool response."""
    review = AI_REVIEW.get(step)
    if review:
        payload = dict(payload)
        payload["ai_review"] = review
    return payload
