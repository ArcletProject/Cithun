from arclet.cithun import PermissionService, PermissionEngine


class DefaultPermissionService(PermissionService[dict]):
    engine: PermissionEngine[dict]

