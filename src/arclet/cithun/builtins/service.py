from arclet.cithun import PermissionEngine, PermissionService


class DefaultPermissionService(PermissionService[dict]):
    engine: PermissionEngine[dict]
