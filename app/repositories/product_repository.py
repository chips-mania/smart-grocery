from app.cache.startup_cache import get_cache
from app.repositories.base_repository import BaseRepository

PRODUCT_SELECT = (
    "product_id,name,description,price,discount_price,discount_rate,"
    "category_name,package_amount,package_unit,package_count,"
    "package_count_unit"
)


class ProductRepository(BaseRepository):

    def get_product(self, product_id: int) -> dict | None:
        cache = get_cache()
        if cache.is_loaded:
            return cache.get_product(product_id)

        response = (
            self.db.table("products_v3")
            .select(PRODUCT_SELECT)
            .eq("product_id", product_id)
            .maybe_single()
            .execute()
        )
        return response.data

    def match_by_embedding(
        self,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[dict]:
        response = self.db.rpc(
            "match_products_v3",
            {
                "query_embedding": query_embedding,
                "match_count": limit,
            },
        ).execute()
        return response.data or []

    def get_ingredient_embedding(self, canonical: str) -> list[float] | None:
        response = (
            self.db.table("ingredient_vectors_v3")
            .select("embedding")
            .eq("canonical_ingredient", canonical)
            .maybe_single()
            .execute()
        )
        if not response.data:
            return None
        return response.data.get("embedding")

    def match_ingredient_canonicals(
        self,
        query_embedding: list[float],
        limit: int = 5,
    ) -> list[dict]:
        response = self.db.rpc(
            "match_ingredient_vectors_v3",
            {
                "query_embedding": query_embedding,
                "match_count": limit,
            },
        ).execute()
        return response.data or []
