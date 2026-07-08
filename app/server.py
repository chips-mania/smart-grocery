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
from app.tools.agentic_meal import kurly_search
from app.tools.agentic_meal import plan_one_meal
from app.tools.agentic_meal import search_recipes
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
        "Smart Grocery(알뜰장보기) PRIMARY tool. One call: search recipes, build soup+main+side tray, "
        "simulate Kurly shopping, return menu_ingredients, buy_list, shopping_selections, "
        "leftover_score, total_price. Use for fridge leftovers and menu/shopping requests. "
        "fridge_items: [{\"ingredient\":\"돼지고기\"}] or name key. query optional (e.g. 된장찌개)."
    ),
    annotations=OPENWORLD_ANNOTATIONS,
)(plan_one_meal)

mcp.tool(
    name="search_recipes",
    title="Search Recipes",
    description=(
        "Smart Grocery(알뜰장보기) browse-only recipe search. Use ONLY when user wants candidates "
        "without shopping. For full meal + buy list use plan_one_meal. "
        "fridge_items: ingredient or name key. category: soup|main|side."
    ),
    annotations=READONLY_ANNOTATIONS,
)(search_recipes)

mcp.tool(
    name="kurly_search",
    title="Search Kurly Products",
    description=(
        "Search Kurly for one keyword (e.g. 두부). Use when user asks to find a product on Kurly. "
        "For full meal planning use plan_one_meal instead."
    ),
    annotations=OPENWORLD_ANNOTATIONS,
)(kurly_search)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
