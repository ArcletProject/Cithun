from __future__ import annotations

from .store import BaseStore
from .service import PermissionService
from .model import AclEntry, Permission, ResourceNode, User, Role
class PermissionNotFoundError(KeyError):
    """资源不存在或父资源不存在时抛出。"""
    pass


class PermissionDeniedError(PermissionError):
    """权限不足时抛出。"""
    pass


class PermissionExecutor:
    """
    专门负责对“权限状态”的 get/set 操作。

    这里的“权限状态”定义为：某个 subject 在某个资源节点上的有效权限 bitmask（int）。

    - suget / suset : 以 root 身份操作（无权限检查）
    - get / set     : 以执行者（某个 User）身份操作，并按题设规则做检查
    """

    def __init__(
        self,
        storage: BaseStore,
        perm_service: PermissionService,
    ):
        self.storage = storage
        self.perm_service = perm_service

    # ---------- 工具方法 ----------

    def _get_parent_and_self(
        self,
        resource_path: str,
        missing_ok: bool,
    ) -> tuple[ResourceNode | None, ResourceNode | None]:
        """
        返回 (parent_node, self_node)，其中任意一个可能为 None（若不存在）。
        如果 missing_ok=False 时，按规则抛出 PermissionNotFoundError。
        """
        path = resource_path.strip("/")
        if not path:
            # 根节点没有父节点的概念，这里约定 parent=None, self=root(如果存在)
            root = self.storage.resources.get("root")
            if root is None and not missing_ok:
                raise PermissionNotFoundError("Root resource 'root' does not exist")
            return None, root

        # 获取 self
        self_node = self.storage.resources.get(path)
        # 获取 parent
        if "/" in path:
            parent_id = path.rsplit("/", 1)[0]
        else:
            parent_id = None
        parent_node = self.storage.resources.get(parent_id) if parent_id else None

        # 父节点不存在
        if parent_node is None and parent_id is not None and not missing_ok:
            raise PermissionNotFoundError(f"Parent resource '{parent_id}' not found")

        # 自身不存在
        if self_node is None and not missing_ok:
            raise PermissionNotFoundError(f"Resource '{path}' not found")

        return parent_node, self_node

    def _ensure_resource_for_set(
        self,
        resource_path: str,
        missing_ok: bool,
    ) -> tuple[ResourceNode | None, ResourceNode]:
        """
        set/suset 时使用：
        - 若自身不存在且 missing_ok=False：抛异常
        - 若自身不存在且 missing_ok=True：允许自动创建（通过 define）
        """
        parent, node = self._get_parent_and_self(resource_path, missing_ok=missing_ok)
        if node is None:
            if not missing_ok:
                raise PermissionNotFoundError(f"Resource '{resource_path}' not found")
            # 自动创建
            node = self.storage.define(resource_path)
        return parent, node

    def _get_primary_acl(
        self,
        subject: User | Role,
        resource_id: str,
    ) -> AclEntry | None:
        """
        返回第一个匹配 subject+resource 的 ACL，视为主 ACL。
        若不存在则返回 None。
        """
        for acl in self.storage.acls:
            if (acl.subject_type == subject.type and
                    acl.subject_id == subject.id and
                    acl.resource_id == resource_id):
                return acl
        return None

    def _apply_chmod(
        self,
        old_mask: int,
        mask: int,
        mode: str,
    ) -> int:
        """
        chmod 风格权限调整：
        - mode="=" : 覆盖为 mask
        - mode="+" : old_mask | mask
        - mode="-" : old_mask & ~mask
        """
        if mode == "=":
            return mask
        elif mode == "+":
            return old_mask | mask
        elif mode == "-":
            return old_mask & ~mask
        else:
            raise ValueError(f"Unsupported chmod mode: {mode!r}")

    # ---------- suget：root 获取执行者在某节点的权限状态 ----------

    def suget(
        self,
        subject: User | Role,
        resource_path: str,
        missing_ok: bool = False,
        context: tuple | None = None,
    ) -> int | None:
        """
        root 获取 subject 在指定节点上的权限状态（bitmask），不做权限校验。

        规则：
          1. 若父节点不存在 -> missing_ok=False: 抛异常；missing_ok=True: 返回 None
          2. 若自身不存在   -> missing_ok=False: 抛异常；missing_ok=True: 返回 None
        """
        parent, node = self._get_parent_and_self(resource_path, missing_ok=missing_ok)
        # 若 missing_ok=True，则 parent 或 node 可能为 None，此时按规则返回 None
        if node is None:
            return None

        context = context or ()

        # 直接用内部方法计算该 subject 的静态权限
        cache: dict[tuple[str, str, str], int] = {}
        mask = self.perm_service._calc_permissions_for_subject(
            subject.type,
            subject.id,
            node,
            context,
            visited=[],
            cache=cache,
        )
        return mask
    
    def test(
        self,
        subject: User | Role,
        resource_path: str,
        required_mask: int,
        missing_ok: bool = False,
        context: tuple | None = None,
    ) -> bool:
        """
        root 测试 subject 在指定节点上是否拥有某些权限，不做权限校验。

        规则：
          1. 若父节点不存在 -> missing_ok=False: 抛异常；missing_ok=True: 返回 False
          2. 若自身不存在   -> missing_ok=False: 抛异常；missing_ok=True: 返回 False
        """
        mask = self.suget(
            subject,
            resource_path,
            missing_ok=missing_ok,
            context=context,
        )
        if mask is None:
            mask = Permission.VISIT | Permission.AVAILABLE
        return (mask & required_mask) == required_mask

    # ---------- get：执行者获取自己在目标节点的权限状态 ----------

    def get(
        self,
        executor: User,
        resource_path: str,
        missing_ok: bool = False,
        context: tuple | None = None,
    ) -> int | None:
        """
        执行者获取自己在目标节点的权限状态。

        规则：
          1. 若父节点不存在 -> missing_ok=False: 抛异常；missing_ok=True: 返回 None
          2. 执行者在父节点的权限不包含 v+a -> 抛 PermissionDeniedError
          3. 若自身不存在 -> missing_ok=False: 抛异常；missing_ok=True: 返回 None
          4. 执行者在自身的权限不包含 v -> 抛 PermissionDeniedError；否则返回权限状态
        """
        parent, node = self._get_parent_and_self(resource_path, missing_ok=missing_ok)
        context = context or ()

        # 2. 检查执行者在父节点是否有 v+a（VISIT + AVAILABLE）
        if parent is not None:
            parent_mask = self.perm_service.get_effective_permissions(
                executor, parent.id, context
            )
            required_parent = Permission.VISIT | Permission.AVAILABLE
            if (parent_mask & required_parent) != required_parent:
                raise PermissionDeniedError(
                    f"Executor '{executor.id}' lacks VISIT+AVAILABLE on parent '{parent.id}'"
                )

        # 3. 自身不存在
        if node is None:
            return None

        # 4. 检查自身权限包含 VISIT
        self_mask = self.perm_service.get_effective_permissions(
            executor, node.id, context
        )
        if (self_mask & Permission.VISIT) != Permission.VISIT:
            raise PermissionDeniedError(
                f"Executor '{executor.id}' lacks VISIT on '{node.id}'"
            )
        return self_mask

    # ---------- suset：root 设置权限状态 ----------

    def suset(
        self,
        subject: User | Role,
        resource_path: str,
        mask: int,
        mode: str = "=",
        missing_ok: bool = False,
    ) -> AclEntry:
        """
        root 为 subject 在指定节点上“设置权限状态”。

        这里示例实现为：
        - 先删除该 subject 在该 resource 上的旧 ACL（若你要支持多条 ACL，可改为添加一条新的而不删除旧的）
        - 再创建一条 allow_mask=new_mask 的 ACL

        规则：
          1. 若父节点不存在 -> missing_ok=False: 抛异常
          2. 若自身不存在 -> missing_ok=False: 抛异常；missing_ok=True: 可自动创建节点
          3. mode 支持 "=", "+", "-" 三种风格
            - "=" : 直接覆盖为 mask
            - "+" : 在旧权限基础上增加 mask
            - "-" : 在旧权限基础上删除 mask
        """
        _, node = self._ensure_resource_for_set(resource_path, missing_ok=missing_ok)

        # 删除旧 ACL（简单实现：同 subject + 同 resource 的都删）
        # self.storage.acls = [
        #     acl for acl in self.storage.acls
        #     if not (acl.subject_type == subject.type and
        #             acl.subject_id == subject.id and
        #             acl.resource_id == node.id)
        # ]
        # # 设置新 ACL
        # return self.storage.assign(
        #     subject=subject,
        #     resource_path=node.id,  # 这里使用节点 id（已经是标准化 path）
        #     allow_mask=new_mask,
        primary_acl = self._get_primary_acl(subject, node.id)
        old_mask = primary_acl.allow_mask if primary_acl else 0
        new_mask = self._apply_chmod(old_mask, mask, mode)
        if primary_acl:
            # 更新已有 ACL
            primary_acl.allow_mask = new_mask
            return primary_acl
        else:
            # 创建新 ACL
            return self.storage.assign(
                subject=subject,
                resource_path=node.id,
                allow_mask=new_mask,
            )

    # ---------- set：执行者设置目标节点的权限状态 ----------

    def set(
        self,
        executor: User,
        target: User | Role,
        resource_path: str,
        mask: int,
        mode: str = "=",
        missing_ok: bool = False,
        context: tuple | None = None,
    ) -> AclEntry | None:
        """
        执行者为目标 subject 设置目标节点的权限状态。

        规则：
          1. 若父节点不存在 -> missing_ok=False: 抛异常
          2. 执行者在父节点权限不包含 v+m+a -> 抛 PermissionDeniedError
          3. 若自身不存在 -> missing_ok=False: 抛异常；missing_ok=True: 可自动创建节点
          4. 执行者在自身的权限不包含 m -> 不修改该节点状态（静默返回）
          5. mode 支持 "=", "+", "-" 三种风格
            - "=" : 直接覆盖为 mask
            - "+" : 在旧权限基础上增加 mask
            - "-" : 在旧权限基础上删除 mask
        """
        context = context or ()

        parent, node = self._ensure_resource_for_set(resource_path, missing_ok=missing_ok)

        # 2. 检查执行者在父节点是否有 v+m+a
        if parent is not None:
            parent_mask = self.perm_service.get_effective_permissions(
                executor, parent.id, context
            )
            required_parent = Permission.VISIT | Permission.MODIFY | Permission.AVAILABLE
            if (parent_mask & required_parent) != required_parent:
                raise PermissionDeniedError(
                    f"Executor '{executor.id}' lacks V+M+A on parent '{parent.id}'"
                )

        # 4. 检查执行者在自身是否有 MODIFY
        self_mask = self.perm_service.get_effective_permissions(
            executor, node.id, context
        )
        if (self_mask & Permission.MODIFY) != Permission.MODIFY:
            # 不修改该节点状态
            return

        primary_acl = self._get_primary_acl(target, node.id)
        old_mask = primary_acl.allow_mask if primary_acl else 0
        new_mask = self._apply_chmod(old_mask, mask, mode)
        if primary_acl:
            # 更新已有 ACL
            primary_acl.allow_mask = new_mask
            return primary_acl
        else:
            # 创建新 ACL
            return self.storage.assign(
                subject=target,
                resource_path=node.id,
                allow_mask=new_mask,
            )
