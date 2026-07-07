from typing import Iterable, TypeVar

from etl.common.logger import info
from etl.common.supabase_client import supabase

T = TypeVar("T")


def chunk(data: Iterable[T], size: int):
    """
    데이터를 size 단위로 분할
    """

    data = list(data)

    for i in range(0, len(data), size):
        yield data[i:i + size]


def batch_insert(
    table_name: str,
    rows: list,
    batch_size: int = 500,
):
    """
    INSERT 전용
    (recipe_ingredients 등에 사용)
    """

    if not rows:
        info(f"{table_name}: nothing to insert")
        return

    total = len(rows)

    uploaded = 0

    info(f"{table_name}: inserting {total} rows")

    for batch in chunk(rows, batch_size):

        supabase.table(table_name).insert(batch).execute()

        uploaded += len(batch)

        info(f"{table_name}: {uploaded}/{total}")

    info(f"{table_name}: insert complete")


def batch_upsert(
    table_name: str,
    rows: list,
    batch_size: int = 500,
    on_conflict: str | None = None,
):
    """
    UPSERT 전용
    (recipes, kurly_products 등에 사용)
    """

    if not rows:
        info(f"{table_name}: nothing to upsert")
        return

    total = len(rows)

    uploaded = 0

    info(f"{table_name}: upserting {total} rows")

    for batch in chunk(rows, batch_size):

        if on_conflict:
            (
                supabase
                .table(table_name)
                .upsert(batch, on_conflict=on_conflict)
                .execute()
            )
        else:
            (
                supabase
                .table(table_name)
                .upsert(batch)
                .execute()
            )

        uploaded += len(batch)

        info(f"{table_name}: {uploaded}/{total}")

    info(f"{table_name}: upsert complete")