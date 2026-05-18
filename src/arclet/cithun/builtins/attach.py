import fnmatch
import re
from collections.abc import Callable
from typing import TypeAlias, TypeVar, overload

from arclet.cithun import Permission, PermissionEngine, ResourceNode, Role, User

Attach: TypeAlias = Callable[
    [User, dict | None, Permission, Callable[[User | Role, dict | None], Permission]],
    Permission | tuple[Permission, str],
]
TAttach = TypeVar("TAttach", bound=Attach)
Attach1: TypeAlias = Callable[
    [User, str, dict | None, Permission, Callable[[User | Role, dict | None], Permission]],
    Permission | tuple[Permission, str],
]
TAttach1 = TypeVar("TAttach1", bound=Attach1)


class Attacher:
    """资源级别的权限策略绑定器。

    将函数注册为特定资源节点上的策略回调，在权限计算时按注册顺序依次执行。
    每个回调接收静态 ACL 计算出的初始掩码，返回修改后的掩码或 (掩码, 模式) 元组。

    Returns:
        Permission: 叠加当前位 (裸返回，等价于 ``"+ "``)
        (Permission, str): 模式 ``"+"`` 叠加、``"-"`` 移除、``"="`` 覆盖
    """

    def __init__(self, engine: PermissionEngine[dict]):
        self.attachs: list[tuple[Callable[[str], bool], Callable[..., Permission | tuple[Permission, str]]]] = []
        engine.register_strategy(self._run_attachs)

    def _run_attachs(
        self,
        user: User,
        resource: ResourceNode,
        context: dict | None,
        current_mask: Permission,
        permission_lookup: Callable[[User | Role, dict | None], Permission],
    ) -> Permission:
        """内部策略回调，遍历所有已绑定的 attach 函数并依次应用。

        Args:
            user: 当前用户。
            resource: 目标资源节点。
            context: 权限计算上下文。
            current_mask: 静态 ACL 计算出的初始掩码。
            permission_lookup: 查询其他主体权限的回调。

        Returns:
            Permission: 所有 attach 函数应用后的最终权限掩码。
        """
        result = current_mask
        for pattern, func in self.attachs:
            if pattern(resource.id):
                ret = func(user, resource.id, context, current_mask, permission_lookup)
                if isinstance(ret, tuple):
                    mask, mode = ret
                    if mode == "=":
                        result = mask
                    elif mode == "-":
                        result &= ~mask
                    else:
                        result |= mask
                else:
                    result |= ret
        return result

    @overload
    def attach(self, pattern: str) -> Callable[[TAttach], TAttach]: ...

    @overload
    def attach(self, pattern: Callable[[str], bool]) -> Callable[[TAttach1], TAttach1]: ...

    def attach(self, pattern):  # type: ignore
        """注册资源级权限回调。

        当 pattern 为字符串时，支持 glob 通配 (``*`` / ``?`` / ``[]``)。
        回调在对应资源节点被访问时触发。

        Args:
            pattern: 资源匹配模式。字符串精确匹配或 glob 通配，或自定义谓词函数。

        Returns:
            装饰器，将函数注册为 attach 回调。

        回调签名::

            (user, context, current_mask, permission_lookup) -> Permission | tuple[Permission, str]

        - 裸 ``Permission``: 与当前掩码叠加 (等价 ``"+"``)
        - ``(Permission, "+")``: 叠加
        - ``(Permission, "-")``: 从当前掩码中移除
        - ``(Permission, "=")``: 覆盖当前掩码
        """
        if isinstance(pattern, str):

            def decorator(func: Attach, /):
                if re.search(r"[*?\[\]]", pattern):
                    predicate = lambda p: fnmatch.fnmatch(p, pattern)
                else:
                    predicate = lambda p: p == pattern
                self.attachs.append((predicate, lambda u, _, *args: func(u, *args)))
                return func

            return decorator

        def wrapper(func: Attach1, /):
            self.attachs.append((pattern, func))
            return func

        return wrapper
