import os
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from app.cache.startup_cache import get_cache
from app.tools.agentic_meal import (
    aggregate_buy_list,
    evaluate_meal_tray,
    kurly_search,
    pick_best_meal_tray,
    plan_one_meal,
    propose_meal_trays,
    score_leftovers,
    search_recipes,
    select_product_min_waste,
)
from app.tools.orchestrator_instructions import MCP_SERVER_INSTRUCTIONS


@asynccontextmanager
async def lifespan(_server: FastMCP):
    get_cache().load()
    yield


READONLY_ANNOTATIONS = ToolAnnotations(
    title="Smart Grocery Read Tool",
    readOnlyHint=True,
    destructiveHint=False,
    openWorldHint=False,
    idempotentHint=True,
)

OPENWORLD_ANNOTATIONS = ToolAnnotations(
    title="Smart Grocery External Lookup Tool",
    readOnlyHint=True,
    destructiveHint=False,
    openWorldHint=True,
    idempotentHint=True,
)


mcp = FastMCP(
    "smart-grocery",
    instructions=MCP_SERVER_INSTRUCTIONS,
    host="0.0.0.0",
    port=int(os.getenv("PORT", "8000")),
    stateless_http=True,
    streamable_http_path="/mcp",
    lifespan=lifespan,
)

mcp.tool(
    name="search_recipes",
    title="Search Recipes",
    description=(
        "Search recipes in Smart Grocery(알뜰장보기) by dish name and/or fridge leftover ingredients. "
        "Returns candidates WITH full ingredient lists. Prefer high fridge coverage. "
        "Orchestrator MUST review and drop weak matches before next step."
    ),
    annotations=READONLY_ANNOTATIONS,
)(search_recipes)

mcp.tool(
    name="propose_meal_trays",
    title="Propose Meal Trays",
    description=(
        "From Smart Grocery(알뜰장보기) recipe candidates, propose one-meal trays: soup + main + side (no rice). "
        "Ranks by shared ingredients and fewer purchases (leftover proxy before shopping). "
        "Orchestrator MUST verify every slot is a real recipe with correct category."
    ),
    annotations=READONLY_ANNOTATIONS,
)(propose_meal_trays)

mcp.tool(
    name="evaluate_meal_tray",
    title="Evaluate Meal Tray",
    description=(
        "Simulate Smart Grocery(알뜰장보기) joint shopping for one complete tray (3 recipe_ids). "
        "Returns leftover_score, total_price, and per-ingredient leftovers."
    ),
    annotations=OPENWORLD_ANNOTATIONS,
)(evaluate_meal_tray)

mcp.tool(
    name="pick_best_meal_tray",
    title="Pick Best Meal Tray",
    description=(
        "Run Smart Grocery(알뜰장보기) meal-tray evaluation on multiple tray candidates from propose_meal_trays "
        "and return the tray with the lowest leftover_score (primary objective)."
    ),
    annotations=OPENWORLD_ANNOTATIONS,
)(pick_best_meal_tray)

mcp.tool(
    name="plan_one_meal",
    title="Plan One Meal",
    description=(
        "End-to-end one meal in Smart Grocery(알뜰장보기): search recipes, propose trays, simulate shopping for "
        "top candidates, pick lowest leftover. Returns menu, price, leftovers."
    ),
    annotations=OPENWORLD_ANNOTATIONS,
)(plan_one_meal)

mcp.tool(
    name="aggregate_buy_list",
    title="Aggregate Buy List",
    description=(
        "Merge Smart Grocery(알뜰장보기) selected tray recipes into one buy list after subtracting fridge and pantry. "
        "Call this before kurly_search so shared ingredients are purchased once."
    ),
    annotations=READONLY_ANNOTATIONS,
)(aggregate_buy_list)

mcp.tool(
    name="kurly_search",
    title="Search Kurly Products",
    description=(
        "Search Kurly products for Smart Grocery(알뜰장보기) by keyword using the live catalog API. "
        "Returns candidates; YOU must remove irrelevant products before select_product_min_waste."
    ),
    annotations=OPENWORLD_ANNOTATIONS,
)(kurly_search)

mcp.tool(
    name="select_product_min_waste",
    title="Select Product Min Waste",
    description=(
        "From AI-filtered Kurly candidates in Smart Grocery(알뜰장보기), pick the product that minimizes leftover "
        "vs required amount/count. Price is only a tie-breaker."
    ),
    annotations=READONLY_ANNOTATIONS,
)(select_product_min_waste)

mcp.tool(
    name="score_leftovers",
    title="Score Leftovers",
    description=(
        "Score confirmed Smart Grocery(알뜰장보기) product selections by estimated leftover volume. "
        "Lower leftover_score is better. Use to compare trays or decide replacements."
    ),
    annotations=READONLY_ANNOTATIONS,
)(score_leftovers)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
