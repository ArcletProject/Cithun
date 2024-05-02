from collections import UserDict
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Literal


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

    def satisfied(self, other: "Context", mode: Literal["least_one", "all"] = "least_one") -> bool:
        if not self.data:
            return True
        if not other.data:
            return True
        return self.contain_all(other) if mode == "all" else self.contain_least(other)

    def contain_all(self, other: "Context"):
        return self.data == other.data

    def contain_least(self, other: "Context"):
        return any((other.get(k) == v for k, v in self.data.items()))


_ctx = ContextVar("context")


@contextmanager
def context(**kwargs):
    token = _ctx.set(Context(**kwargs))
    try:
        yield
    finally:
        _ctx.reset(token)
