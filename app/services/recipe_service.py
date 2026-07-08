from app.cache.recipe_engagement import recipe_inq_cnt
from app.repositories.recipe_repository import RecipeRepository
from app.services.menu_matcher import (
    MIN_MATCH_SCORE,
    build_resolution_entry,
    score_menu_match,
)

VECTOR_FALLBACK_MIN_SCORE = 0.35


class RecipeService:

    def __init__(self):
        self.recipe_repository = RecipeRepository()

    def search_recipe(self, keyword: str, limit: int = 20):
        return self.recipe_repository.search_recipe(keyword=keyword, limit=limit)

    def get_recipe(self, recipe_id: int):
        return self.recipe_repository.get_recipe(recipe_id)

    def get_ingredients(self, recipe_id: int):
        return self.recipe_repository.get_ingredients(recipe_id)

    def get_all_recipes(self):
        return self.recipe_repository.get_all()

    def get_recipes_by_names(self, names: list[str]):
        return self.recipe_repository.get_by_names(names)

    def _vector_candidates(self, query: str, limit: int = 10) -> list[dict]:
        try:
            from etl.common.bge_client import embed_query
        except Exception:  # noqa: BLE001
            return []

        embedding = embed_query(query)
        return self.recipe_repository.match_by_embedding(embedding, limit=limit)

    def resolve_menu_name(self, query: str) -> dict | None:
        exact_matches = self.get_recipes_by_names([query])
        if exact_matches:
            recipe = exact_matches[0]
            return build_resolution_entry(
                query=query,
                recipe=recipe,
                score=1.0,
                alternatives=[],
            )

        candidates = self.search_recipe(query, limit=20)
        scored: list[tuple[float, dict]] = []

        for recipe in candidates:
            score = score_menu_match(query, recipe["name"])
            if score >= MIN_MATCH_SCORE:
                scored.append((score, recipe))

        if not scored:
            for recipe in self._vector_candidates(query, limit=10):
                score = score_menu_match(query, recipe["name"])
                if score <= 0:
                    # cosine distance: lower is better; map to soft score
                    distance = float(recipe.get("distance") or 1.0)
                    score = max(0.0, 1.0 - distance)
                if score >= VECTOR_FALLBACK_MIN_SCORE:
                    scored.append((score, recipe))

        if not scored:
            return None

        scored.sort(key=lambda item: (-item[0], -recipe_inq_cnt(item[1]), item[1]["name"]))
        best_score, best_recipe = scored[0]
        alternatives = [
            recipe["name"]
            for score, recipe in scored[1:4]
            if recipe["recipe_id"] != best_recipe["recipe_id"]
        ]

        return build_resolution_entry(
            query=query,
            recipe=best_recipe,
            score=best_score,
            alternatives=alternatives,
        )

    def resolve_menu_names(self, names: list[str]) -> tuple[list[dict], list[dict]]:
        resolutions: list[dict] = []
        recipes: list[dict] = []
        seen_ids: set[int] = set()

        for name in names:
            resolution = self.resolve_menu_name(name)
            if resolution is None:
                continue

            resolutions.append(resolution)
            recipe = resolution["recipe"]
            if recipe["recipe_id"] in seen_ids:
                continue

            recipes.append(recipe)
            seen_ids.add(recipe["recipe_id"])

        return recipes, resolutions
