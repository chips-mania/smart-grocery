import os
import threading
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.responses import Response

from app.cache.startup_cache import StartupCache
from app.cache.startup_cache import get_cache
from app.common.logger import error
from app.common.logger import info
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


def _load_cache_background() -> None:
    try:
        get_cache().load()
        info("startup cache loaded")
    except Exception as exc:
        error(f"startup cache load failed: {exc}")


@asynccontextmanager
async def lifespan(_server: FastMCP):
    port = os.getenv("PORT", "8000")
    has_url = bool(os.getenv("SUPABASE_URL"))
    has_key = bool(os.getenv("SUPABASE_KEY"))
    info(f"smart-grocery-mcp starting port={port} SUPABASE_URL={'set' if has_url else 'MISSING'} SUPABASE_KEY={'set' if has_key else 'MISSING'}")
    if not has_url or not has_key:
        error("SUPABASE_URL / SUPABASE_KEY must be configured in PlayMCP env settings")
    threading.Thread(target=_load_cache_background, daemon=True).start()
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


@mcp.custom_route("/health", methods=["GET"])
async def health(_request: Request) -> Response:
    cache = StartupCache.instance()
    return JSONResponse(
        {
            "status": "ok",
            "service": "smart-grocery-mcp",
            "cache_loaded": cache.is_loaded,
        }
    )


@mcp.custom_route("/", methods=["GET"])
async def root(_request: Request) -> Response:
    return JSONResponse({"status": "ok", "mcp": "/mcp"})


mcp.tool(
    name="search_recipes",
    title="Search Recipes",
    description=(
        "Search recipes in Smart Grocery(알뜰장보기) by dish name and/or fridge items. "
        "fridge_items: [{\"ingredient\":\"돼지고기\"}] (name key also ok). "
        "category optional: soup|main|side or 국&찌개|일품|반찬. "
        "Returns recipe_id, name, category, buy_ingredients (compact). limit default 8, max 15."
    ),
    annotations=READONLY_ANNOTATIONS,
)(search_recipes)

mcp.tool(
    name="propose_meal_trays",
    title="Propose Meal Trays",
    description=(
        "From Smart Grocery(알뜰장보기) search_recipes candidates, build one-meal trays: "
        "soup(국&찌개) + main(일품) + side(반찬), no rice. "
        "Pass recipes array with recipe_id. fridge_items: ingredient or name key. "
        "Optional soup_recipe_id to fix soup slot. Verify each slot is a real recipe name."
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
        "Smart Grocery(알뜰장보기) end-to-end one meal: search → trays → Kurly simulation → "
        "lowest leftover_score. Use query for menu (e.g. 된장찌개). "
        "fridge_items: [{\"ingredient\":\"두부\"}] or name key. Prefer this over calling many tools."
    ),
    annotations=OPENWORLD_ANNOTATIONS,
)(plan_one_meal)

mcp.tool(
    name="aggregate_buy_list",
    title="Aggregate Buy List",
    description=(
        "Smart Grocery(알뜰장보기) merge tray recipes into one buy list; subtract fridge and pantry staples. "
        "recipes need recipe_id. fridge_items: ingredient or name key. "
        "Use before kurly_search per ingredient."
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
