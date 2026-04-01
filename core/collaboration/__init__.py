"""
NovaHands 协作系统

提供团队协作、技能共享、任务管理等企业级协作功能。
"""

from .user_manager import UserManager, TeamManager, User, Team, UserRole, TeamPlan
from .permission_manager import PermissionManager, Permission
from .skill_sharing import SkillSharingManager, SharedSkill, SkillVisibility
from .task_manager import TaskManager, Task, TaskStatus, TaskPriority, TaskType
from .activity_log import ActivityLogger, ActionType, ResourceType as ActivityResourceType

__all__ = [
    "UserManager",
    "TeamManager",
    "User",
    "Team",
    "UserRole",
    "TeamPlan",
    "PermissionManager",
    "Permission",
    "SkillSharingManager",
    "SharedSkill",
    "SkillVisibility",
    "TaskManager",
    "Task",
    "TaskStatus",
    "TaskPriority",
    "TaskType",
    "ActivityLogger",
    "ActionType",
    "ActivityResourceType",
]
