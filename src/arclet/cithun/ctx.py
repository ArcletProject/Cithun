from collections import UserDict
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Dict, Generic, TypeVar


class Context(UserDict):
    @staticmethod
    def current() -> "Context":
        return _ctx.get(Context())

    def __hash__(self):
        _res = []
        _size = 0
        for k, v in self.data.items():
            _res.append(k.__hash__() ^ v.__hash__())
            _size += len(k) + len(v)
        return hash(tuple(_res) + (_size,))

    def __repr__(self):
        return f"[{'|'.join(f'{k}={v}' for k, v in self.data.items())}]" if self.data else "[none]"

    @classmethod
    def from_string(cls, data: str):
        _data = {}
        if data != "[none]":
            for seg in data[1:-2].split("|"):
                segs = seg.split("=")
                _data[segs[0]] = segs[1]
        return cls(**_data)


_ctx = ContextVar("context")


@contextmanager
def context(**kwargs):
    token = _ctx.set(Context(**kwargs))
    try:
        yield
    finally:
        _ctx.reset(token)


class Satisfier:
    @staticmethod
    def all():
        return Satisfier(lambda self, other: self.data == other.data)

    @staticmethod
    def least():
        return Satisfier(lambda self, other: any((other.get(k) == v for k, v in self.data.items())))

    def __init__(self, func: Callable[[Context, Context], bool]):
        self.func = func

    def __call__(self, target: "Context", other: "Context") -> bool:
        if not target.data:
            return True
        if not other.data:
            return True
        return self.func(target, other)


T = TypeVar("T")


class Result(Generic[T]):
    def __init__(self, data: Dict[Context, T], origin: Context):
        self.data = data
        self.origin = origin

    @property
    def most(self) -> T:
        if self.origin in self.data:
            return self.data[self.origin]
        sortd = sorted(
            self.data.keys(), key=lambda x: sum((x.get(k) == v for k, v in self.origin.items())), reverse=True
        )
        return self.data[sortd[0]]

    def __repr__(self):
        return f"Result({self.data})"
