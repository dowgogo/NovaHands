"""
权限管理模块

提供基于角色的访问控制（RBAC）系统。
"""

from typing import Dict, Set, List, Optional
from enum import Enum
from .user_manager import UserRole


class ResourceType(Enum):
    """资源类型"""
    SKILL = "skill"
    TASK = "task"
    TEAM = "team"
    SYSTEM = "system"


class Permission(Enum):
    """权限类型"""
    # 技能权限
    SKILL_CREATE = "skill.create"
    SKILL_READ = "skill.read"
    SKILL_UPDATE = "skill.update"
    SKILL_DELETE = "skill.delete"
    SKILL_PUBLISH = "skill.publish"
    SKILL_SHARE = "skill.share"
    
    # 任务权限
    TASK_CREATE = "task.create"
    TASK_READ = "task.read"
    TASK_UPDATE = "task.update"
    TASK_DELETE = "task.delete"
    TASK_ASSIGN = "task.assign"
    TASK_COMPLETE = "task.complete"
    
    # 团队权限
    TEAM_INVITE = "team.invite"
    TEAM_REMOVE = "team.remove"
    TEAM_MANAGE_ROLES = "team.manage_roles"
    TEAM_VIEW_ANALYTICS = "team.view_analytics"
    
    # 系统权限
    SYSTEM_VIEW_LOGS = "system.view_logs"
    SYSTEM_EXPORT_DATA = "system.export_data"
    SYSTEM_MANAGE_API_KEYS = "system.manage_api_keys"


# 角色权限映射
ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.OWNER: {
        # 技能：完全控制
        Permission.SKILL_CREATE,
        Permission.SKILL_READ,
        Permission.SKILL_UPDATE,
        Permission.SKILL_DELETE,
        Permission.SKILL_PUBLISH,
        Permission.SKILL_SHARE,
        # 任务：完全控制
        Permission.TASK_CREATE,
        Permission.TASK_READ,
        Permission.TASK_UPDATE,
        Permission.TASK_DELETE,
        Permission.TASK_ASSIGN,
        Permission.TASK_COMPLETE,
        # 团队：完全控制
        Permission.TEAM_INVITE,
        Permission.TEAM_REMOVE,
        Permission.TEAM_MANAGE_ROLES,
        Permission.TEAM_VIEW_ANALYTICS,
        # 系统：完全控制
        Permission.SYSTEM_VIEW_LOGS,
        Permission.SYSTEM_EXPORT_DATA,
        Permission.SYSTEM_MANAGE_API_KEYS,
    },
    UserRole.ADMIN: {
        # 技能：创建、编辑、发布
        Permission.SKILL_CREATE,
        Permission.SKILL_READ,
        Permission.SKILL_UPDATE,
        Permission.SKILL_DELETE,
        Permission.SKILL_PUBLISH,
        Permission.SKILL_SHARE,
        # 任务：管理、分配
        Permission.TASK_CREATE,
        Permission.TASK_READ,
        Permission.TASK_UPDATE,
        Permission.TASK_DELETE,
        Permission.TASK_ASSIGN,
        Permission.TASK_COMPLETE,
        # 团队：管理成员
        Permission.TEAM_INVITE,
        Permission.TEAM_REMOVE,
        Permission.TEAM_MANAGE_ROLES,
        Permission.TEAM_VIEW_ANALYTICS,
        # 系统：部分权限
        Permission.SYSTEM_VIEW_LOGS,
        Permission.SYSTEM_EXPORT_DATA,
    },
    UserRole.MEMBER: {
        # 技能：创建、编辑自己的
        Permission.SKILL_CREATE,
        Permission.SKILL_READ,
        Permission.SKILL_UPDATE,
        Permission.SKILL_SHARE,
        # 任务：查看、更新自己的
        Permission.TASK_CREATE,
        Permission.TASK_READ,
        Permission.TASK_UPDATE,
        Permission.TASK_COMPLETE,
        # 团队：无管理权限
        Permission.TEAM_VIEW_ANALYTICS,
        # 系统：无权限
    },
    UserRole.VIEWER: {
        # 技能：仅查看
        Permission.SKILL_READ,
        # 任务：仅查看
        Permission.TASK_READ,
        # 团队：仅查看分析
        Permission.TEAM_VIEW_ANALYTICS,
        # 系统：无权限
    },
}


class PermissionManager:
    """权限管理器"""
    
    def __init__(self):
        # 自定义权限覆盖（user_id -> team_id -> permissions）
        self.custom_permissions: Dict[str, Dict[str, Set[Permission]]] = {}
    
    def has_permission(
        self,
        user_id: str,
        role: UserRole,
        permission: Permission
    ) -> bool:
        """
        检查用户是否有指定权限
        
        Args:
            user_id: 用户 ID
            role: 用户角色
            permission: 要检查的权限
        
        Returns:
            是否有权限
        """
        # 获取角色权限
        role_perms = ROLE_PERMISSIONS.get(role, set())
        
        # 检查权限
        return permission in role_perms
    
    def check_resource_permission(
        self,
        user_id: str,
        role: UserRole,
        resource_type: ResourceType,
        action: str,
        resource_owner_id: Optional[str] = None,
        team_id: Optional[str] = None
    ) -> bool:
        """
        检查用户对指定资源的权限
        
        Args:
            user_id: 用户 ID
            role: 用户角色
            resource_type: 资源类型
            action: 操作类型（create, read, update, delete 等）
            resource_owner_id: 资源所有者 ID
            team_id: 团队 ID（用于检查团队共享规则）
        
        Returns:
            是否有权限
        """
        # 构建权限字符串
        permission_str = f"{resource_type.value}.{action}"
        
        try:
            permission = Permission(permission_str)
        except ValueError:
            return False
        
        # 1. 检查角色权限
        if not self.has_permission(user_id, role, permission):
            return False
        
        # 2. 如果指定了资源所有者，检查是否是所有者
        if resource_owner_id:
            # Owner 和 Admin 可以操作所有资源
            if role in [UserRole.OWNER, UserRole.ADMIN]:
                return True
            
            # Member 只能操作自己的资源（部分权限）
            if role == UserRole.MEMBER:
                # Viewer 只能查看
                if role == UserRole.VIEWER and action != "read":
                    return False
                
                # Member 可以查看和更新自己的资源
                if user_id == resource_owner_id:
                    return action in ["read", "update"]
                
                # Member 可以查看团队共享的资源
                if team_id:
                    return action == "read"
                
                return False
            
            # Viewer 只能查看
            if role == UserRole.VIEWER:
                return action == "read"
        
        return True
    
    def grant_custom_permission(
        self,
        user_id: str,
        team_id: str,
        permission: Permission
    ):
        """
        授予自定义权限
        
        Args:
            user_id: 用户 ID
            team_id: 团队 ID
            permission: 权限
        """
        if user_id not in self.custom_permissions:
            self.custom_permissions[user_id] = {}
        
        if team_id not in self.custom_permissions[user_id]:
            self.custom_permissions[user_id][team_id] = set()
        
        self.custom_permissions[user_id][team_id].add(permission)
    
    def revoke_custom_permission(
        self,
        user_id: str,
        team_id: str,
        permission: Permission
    ):
        """
        撤销自定义权限
        
        Args:
            user_id: 用户 ID
            team_id: 团队 ID
            permission: 权限
        """
        if user_id in self.custom_permissions:
            if team_id in self.custom_permissions[user_id]:
                self.custom_permissions[user_id][team_id].discard(permission)
    
    def get_user_permissions(
        self,
        user_id: str,
        role: UserRole,
        team_id: Optional[str] = None
    ) -> List[str]:
        """
        获取用户的所有权限
        
        Args:
            user_id: 用户 ID
            role: 用户角色
            team_id: 团队 ID（可选，用于获取自定义权限）
        
        Returns:
            权限列表
        """
        # 获取角色权限
        permissions = ROLE_PERMISSIONS.get(role, set()).copy()
        
        # 如果指定了团队 ID，添加自定义权限
        if team_id and user_id in self.custom_permissions:
            custom_perms = self.custom_permissions[user_id].get(team_id, set())
            permissions.update(custom_perms)
        
        return [p.value for p in sorted(permissions, key=lambda x: x.value)]
    
    def get_permission_matrix(
        self,
        role: Optional[UserRole] = None
    ) -> Dict[str, List[str]]:
        """
        获取权限矩阵
        
        Args:
            role: 角色（可选，如果指定则只返回该角色的权限）
        
        Returns:
            权限矩阵（角色 -> 权限列表）
        """
        if role:
            return {role.value: [p.value for p in ROLE_PERMISSIONS.get(role, set())]}
        
        return {
            r.value: [p.value for p in perms]
            for r, perms in ROLE_PERMISSIONS.items()
        }
