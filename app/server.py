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
    kurly_search,
    pick_best_meal_tray,
    plan_one_meal,
    propose_meal_trays,
    search_recipes,
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
    name="plan_one_meal",
    title="Plan One Meal",
    description=(
        "Smart Grocery(알뜰장보기) PRIMARY tool. One call: search → soup+main+side tray → "
        "Kurly simulation → menu_ingredients, buy_list, shopping_selections, leftover_score, "
        "total_price, recommendation_reason. fridge_items: [{\"ingredient\":\"돼지고기\"}] or name key. query optional."
    ),
    annotations=OPENWORLD_ANNOTATIONS,
)(plan_one_meal)

mcp.tool(
    name="search_recipes",
    title="Search Recipes",
    description=(
        "Smart Grocery(알뜰장보기) recipe browse/search by dish name and/or fridge items. "
        "fridge_items: [{\"ingredient\":\"돼지고기\"}] (name key also ok). "
        "category optional: soup|main|side. For full meal + shopping use plan_one_meal."
    ),
    annotations=READONLY_ANNOTATIONS,
)(search_recipes)

mcp.tool(
    name="propose_meal_trays",
    title="Propose Meal Trays",
    description=(
        "Smart Grocery(알뜰장보기) builds soup(국&찌개)+main(일품)+side(반찬) tray candidates "
        "from search_recipes results. Use when plan_one_meal fails or user inspects trays first."
    ),
    annotations=READONLY_ANNOTATIONS,
)(propose_meal_trays)

mcp.tool(
    name="pick_best_meal_tray",
    title="Pick Best Meal Tray",
    description=(
        "Smart Grocery(알뜰장보기) simulates Kurly shopping for propose_meal_trays candidates; "
        "returns lowest leftover_score with buy_list, shopping_selections, recommendation_reason."
    ),
    annotations=OPENWORLD_ANNOTATIONS,
)(pick_best_meal_tray)

mcp.tool(
    name="kurly_search",
    title="Search Kurly Products",
    description=(
        "Smart Grocery(알뜰장보기) searches Kurly for one ingredient keyword (e.g. 두부). "
        "Browse-only; for full meal planning use plan_one_meal instead."
    ),
    annotations=OPENWORLD_ANNOTATIONS,
)(kurly_search)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
