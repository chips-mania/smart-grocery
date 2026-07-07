from typing import Optional

from pydantic import BaseModel


class Product(BaseModel):
    """
    쇼핑몰 상품
    """

    source: str

    source_product_id: int

    ingredient: str

    product_name: str

    package_amount: float | None

    package_unit: str | None

    package_count: float | None

    package_count_unit: str | None

    price: int

    discount_price: Optional[int] = None

    detail_url: str

    image_url: Optional[str] = None