from app.cache.recipe_engagement import sort_recipes_by_inq
from app.cache.startup_cache import get_cache
from postgrest.exceptions import APIError
from app.repositories.base_repository import BaseRepository

RECIPE_SELECT = (
    "recipe_id,name,inq_cnt,category,main_ingredient_group,occasion,"
    "difficulty,servings,method"
)
RECIPE_SELECT_LEGACY = (
    "recipe_id,name,category,main_ingredient_group,occasion,"
    "difficulty,servings,method"
)
INGREDIENT_SELECT = (
    "id,recipe_id,ingredient,canonical_ingredient,amount,unit,"
    "count,role,buy_required"
)


class RecipeRepository(BaseRepository):
    @staticmethod
    def _with_inq(rows: list[dict]) -> list[dict]:
        for row in rows:
            row["inq_cnt"] = int(row.get("inq_cnt") or 0)
        return rows

    def _select_recipes(self, query_builder):
        try:
            response = query_builder(RECIPE_SELECT).execute()
            data = response.data or []
            return self._with_inq(data)
        except APIError as exc:
            if "inq_cnt" not in str(exc):
                raise
            response = query_builder(RECIPE_SELECT_LEGACY).execute()
            data = response.data or []
            return self._with_inq(data)


    def get_recipe(self, recipe_id: int):
        cache = get_cache()
        if cache.is_loaded:
            for recipe in cache.get_recipes():
                if recipe["recipe_id"] == recipe_id:
                    return recipe
            return None

        rows = self._select_recipes(
            lambda cols: self.db.table("recipes_v3")
            .select(cols)
            .eq("recipe_id", recipe_id)
        )
        return rows[0] if rows else None

    def get_ingredients(self, recipe_id: int):
        cache = get_cache()
        if cache.is_loaded:
            return cache.get_ingredients(recipe_id)

        response = (
            self.db.table("recipe_ingredients_v3")
            .select(INGREDIENT_SELECT)
            .eq("recipe_id", recipe_id)
            .execute()
        )
        return response.data

    def search_recipe(self, keyword: str, limit: int = 20):
        cache = get_cache()
        if cache.is_loaded:
            matched = [
                recipe
                for recipe in cache.get_recipes()
                if keyword.lower() in recipe.get("name", "").lower()
            ]
            return sort_recipes_by_inq(matched)[:limit]

        try:
            rows = self._select_recipes(
                lambda cols: self.db.table("recipes_v3")
                .select(cols)
                .ilike("name", f"%{keyword}%")
                .order("inq_cnt", desc=True)
                .limit(limit)
            )
        except APIError as exc:
            if "inq_cnt" not in str(exc):
                raise
            rows = self._select_recipes(
                lambda cols: self.db.table("recipes_v3")
                .select(cols)
                .ilike("name", f"%{keyword}%")
                .limit(limit)
            )
        return sort_recipes_by_inq(rows)[:limit]

    def match_by_embedding(
        self,
        query_embedding: list[float],
        limit: int = 10,
    ) -> list[dict]:
        response = self.db.rpc(
            "match_recipes_v3",
            {
                "query_embedding": query_embedding,
                "match_count": limit,
            },
        ).execute()
        return response.data or []

    def get_by_names(self, names: list[str]):
        if not names:
            return []

        cache = get_cache()
        if cache.is_loaded:
            return cache.get_recipes_by_names(names)

        rows = self._select_recipes(
            lambda cols: self.db.table("recipes_v3")
            .select(cols)
            .in_("name", names)
        )
        return rows

    def get_all(self):
        cache = get_cache()
        if cache.is_loaded:
            return cache.get_recipes()

        return self._select_recipes(lambda cols: self.db.table("recipes_v3").select(cols))
