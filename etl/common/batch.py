from typing import Iterable, List, TypeVar

T = TypeVar("T")


def chunk(data: Iterable[T], size: int = 500):
    """
    리스트를 size 단위로 잘라 반환
    """

    data = list(data)

    for i in range(0, len(data), size):
        yield data[i:i + size]