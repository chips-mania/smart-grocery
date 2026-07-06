from typing import Optional

from pydantic import BaseModel

from app.models.ingredient import Ingredient


class Recipe(BaseModel):
    """
    레시피 정보
    """

    recipe_id: int

    name: str

    category: str

    cook_method: str

    calories: Optional[float] = None

    carbohydrate: Optional[float] = None

    protein: Optional[float] = None

    fat: Optional[float] = None

    sodium: Optional[float] = None

    image_url: Optional[str] = None

    ingredients: list[Ingredient]