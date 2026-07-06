from typing import Optional

from pydantic import BaseModel


class Ingredient(BaseModel):
    """
    레시피에 사용되는 재료
    """

    name: str

    amount: Optional[float] = None

    unit: Optional[str] = None

    raw: Optional[str] = None