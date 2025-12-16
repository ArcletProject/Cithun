class ResourceNotFoundError(FileNotFoundError):
    """资源不存在或父资源不存在时抛出。"""

    pass


class PermissionDeniedError(PermissionError):
    """权限不足时抛出。"""

    pass


class DependencyCycleError(RuntimeError):
    """检测到依赖循环时抛出。"""

    def __init__(self, cycle_nodes: list[tuple[str, str, str]]):
        self.cycle_nodes = cycle_nodes
        msg = "Dependency cycle detected: " + " -> ".join(f"{t}:{sid}@{rid}" for (t, sid, rid) in cycle_nodes)
        super().__init__(msg)
