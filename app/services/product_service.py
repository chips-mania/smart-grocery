from app.parser.product_parser import effective_price
from app.repositories.product_repository import ProductRepository


class ProductService:

    def __init__(self):
        self.product_repository = ProductRepository()

    def _resolve_embedding(self, ingredient: str) -> list[float] | None:
        text = (ingredient or "").strip()
        if not text:
            return None

        embedding = self.product_repository.get_ingredient_embedding(text)
        if embedding:
            return embedding

        from etl.common.bge_client import embed_query

        return embed_query(text)

    def get_products_by_ingredient(
        self,
        ingredient: str,
        preference: str = "minimize_waste",
        limit: int = 5,
    ) -> list[dict]:
        embedding = self._resolve_embedding(ingredient)
        if not embedding:
            return []

        products = self.product_repository.match_by_embedding(
            embedding,
            limit=max(limit, 5),
        )
        for row in products:
            row["search_keyword"] = ingredient

        if preference == "maximize_discount":
            discounted = [p for p in products if (p.get("discount_rate") or 0) > 0]
            if discounted:
                products = discounted

        products.sort(
            key=lambda p: (
                float(p.get("distance") or 999),
                effective_price(p),
            )
        )
        return products[:limit]
