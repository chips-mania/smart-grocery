from typing import Optional

from pydantic import BaseModel


class Ingredient(BaseModel):

    name: str

    # 질량
    amount: float | None = None
    unit: str | None = None

    # 개수
    count: float | None = None
    count_unit: str | None = None

    raw: str | None = None