"""
活动日志模块

记录所有用户操作，提供审计追踪功能。
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set
from enum import Enum


class ActionType(Enum):
    """操作类型"""
    # 用户操作
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_REGISTER = "user.register"
    
    # 技能操作
    SKILL_CREATE = "skill.create"
    SKILL_UPDATE = "skill.update"
    SKILL_DELETE = "skill.delete"
    SKILL_PUBLISH = "skill.publish"
    SKILL_SHARE = "skill.share"
    SKILL_DOWNLOAD = "skill.download"
    
    # 任务操作
    TASK_CREATE = "task.create"
    TASK_ASSIGN = "task.assign"
    TASK_UPDATE = "task.update"
    TASK_COMPLETE = "task.complete"
    TASK_DELETE = "task.delete"
    TASK_COMMENT = "task.comment"
    
    # 团队操作
    TEAM_CREATE = "team.create"
    TEAM_DELETE = "team.delete"
    TEAM_INVITE = "team.invite"
    TEAM_REMOVE = "team.remove"
    TEAM_ROLE_UPDATE = "team.role_update"
    
    # 权限操作
    PERMISSION_GRANT = "permission.grant"
    PERMISSION_REVOKE = "permission.revoke"


class ResourceType(Enum):
    """资源类型"""
    USER = "user"
    SKILL = "skill"
    TASK = "task"
    TEAM = "team"
    PERMISSION = "permission"


class ActivityLog:
    """活动日志条目"""
    
    def __init__(
        self,
        user_id: str,
        user_name: str,
        action: ActionType,
        resource_type: ResourceType,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None
    ):
        self.event_id = str(uuid.uuid4())
        self.user_id = user_id
        self.user_name = user_name
        self.action = action
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.resource_name = resource_name
        self.details = details or {}
        self.ip_address = ip_address
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "action": self.action.value,
            "resource_type": self.resource_type.value,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "details": self.details,
            "ip_address": self.ip_address,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ActivityLog":
        """从字典创建日志条目"""
        log = cls(
            user_id=data["user_id"],
            user_name=data["user_name"],
            action=ActionType(data["action"]),
            resource_type=ResourceType(data["resource_type"]),
            resource_id=data.get("resource_id"),
            resource_name=data.get("resource_name"),
            details=data.get("details"),
            ip_address=data.get("ip_address")
        )
        log.event_id = data["event_id"]
        log.timestamp = datetime.fromisoformat(data["timestamp"])
        return log


class ActivityLogger:
    """活动日志记录器"""
    
    def __init__(self):
        self.logs: List[ActivityLog] = []
    
    def log(
        self,
        user_id: str,
        user_name: str,
        action: ActionType,
        resource_type: ResourceType,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None
    ) -> ActivityLog:
        """
        记录活动日志
        
        Args:
            user_id: 用户 ID
            user_name: 用户名
            action: 操作类型
            resource_type: 资源类型
            resource_id: 资源 ID
            resource_name: 资源名称
            details: 详细信息
            ip_address: IP 地址
        
        Returns:
            日志条目
        """
        log = ActivityLog(
            user_id=user_id,
            user_name=user_name,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            resource_name=resource_name,
            details=details,
            ip_address=ip_address
        )
        self.logs.append(log)
        return log
    
    def get_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[ActionType] = None,
        resource_type: Optional[ResourceType] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[ActivityLog]:
        """
        获取日志
        
        Args:
            user_id: 用户 ID 过滤
            action: 操作类型过滤
            resource_type: 资源类型过滤
            resource_id: 资源 ID 过滤
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
        
        Returns:
            日志列表
        """
        logs = self.logs
        
        # 用户过滤
        if user_id:
            logs = [log for log in logs if log.user_id == user_id]
        
        # 操作类型过滤
        if action:
            logs = [log for log in logs if log.action == action]
        
        # 资源类型过滤
        if resource_type:
            logs = [log for log in logs if log.resource_type == resource_type]
        
        # 资源 ID 过滤
        if resource_id:
            logs = [log for log in logs if log.resource_id == resource_id]
        
        # 时间过滤
        if start_time:
            logs = [log for log in logs if log.timestamp >= start_time]
        
        if end_time:
            logs = [log for log in logs if log.timestamp <= end_time]
        
        # 排序和限制
        logs = sorted(logs, key=lambda x: x.timestamp, reverse=True)
        logs = logs[:limit]
        
        return logs
    
    def get_user_activity_summary(
        self,
        user_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """
        获取用户活动摘要
        
        Args:
            user_id: 用户 ID
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            活动摘要
        """
        logs = self.get_logs(user_id=user_id, start_time=start_time, end_time=end_time)
        
        # 统计
        action_counts = {}
        resource_type_counts = {}
        daily_activity = {}
        
        for log in logs:
            # 操作类型统计
            action = log.action.value
            action_counts[action] = action_counts.get(action, 0) + 1
            
            # 资源类型统计
            resource_type = log.resource_type.value
            resource_type_counts[resource_type] = resource_type_counts.get(resource_type, 0) + 1
            
            # 每日活动统计
            date = log.timestamp.date()
            daily_activity[date] = daily_activity.get(date, 0) + 1
        
        return {
            "user_id": user_id,
            "total_actions": len(logs),
            "action_counts": action_counts,
            "resource_type_counts": resource_type_counts,
            "daily_activity": {
                date.isoformat(): count
                for date, count in sorted(daily_activity.items())
            },
            "first_activity": logs[-1].timestamp.isoformat() if logs else None,
            "last_activity": logs[0].timestamp.isoformat() if logs else None
        }
    
    def get_team_activity_summary(
        self,
        team_id: str,
        team_members: Set[str],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict:
        """
        获取团队活动摘要
        
        Args:
            team_id: 团队 ID
            team_members: 团队成员 ID 集合
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            团队活动摘要
        """
        # 获取所有团队成员的日志
        all_logs = []
        for member_id in team_members:
            member_logs = self.get_logs(
                user_id=member_id,
                start_time=start_time,
                end_time=end_time
            )
            all_logs.extend(member_logs)
        
        # 统计
        user_activity = {}
        action_counts = {}
        daily_activity = {}
        
        for log in all_logs:
            # 用户活动统计
            user_id = log.user_id
            if user_id not in user_activity:
                user_activity[user_id] = {
                    "user_id": user_id,
                    "user_name": log.user_name,
                    "action_count": 0
                }
            user_activity[user_id]["action_count"] += 1
            
            # 操作类型统计
            action = log.action.value
            action_counts[action] = action_counts.get(action, 0) + 1
            
            # 每日活动统计
            date = log.timestamp.date()
            daily_activity[date] = daily_activity.get(date, 0) + 1
        
        return {
            "team_id": team_id,
            "total_actions": len(all_logs),
            "active_members": len(user_activity),
            "user_activity": list(user_activity.values()),
            "action_counts": action_counts,
            "daily_activity": {
                date.isoformat(): count
                for date, count in sorted(daily_activity.items())
            }
        }
    
    def export_to_csv(
        self,
        output_file: str,
        user_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ):
        """
        导出日志到 CSV
        
        Args:
            output_file: 输出文件路径
            user_id: 用户 ID 过滤
            start_time: 开始时间
            end_time: 结束时间
        """
        import csv
        
        logs = self.get_logs(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            limit=10000
        )
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # 写入表头
            writer.writerow([
                "Event ID",
                "Timestamp",
                "User ID",
                "User Name",
                "Action",
                "Resource Type",
                "Resource ID",
                "Resource Name",
                "IP Address",
                "Details"
            ])
            
            # 写入数据
            for log in logs:
                writer.writerow([
                    log.event_id,
                    log.timestamp.isoformat(),
                    log.user_id,
                    log.user_name,
                    log.action.value,
                    log.resource_type.value,
                    log.resource_id or "",
                    log.resource_name or "",
                    log.ip_address or "",
                    str(log.details)
                ])
    
    def clear_old_logs(self, days_to_keep: int = 90):
        """
        清除旧日志
        
        Args:
            days_to_keep: 保留天数
        """
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)
        self.logs = [log for log in self.logs if log.timestamp > cutoff_time]
    
    def get_statistics(self) -> Dict:
        """获取日志统计"""
        total_logs = len(self.logs)
        
        if total_logs == 0:
            return {
                "total_logs": 0,
                "unique_users": 0,
                "action_types": {},
                "resource_types": {}
            }
        
        # 唯一用户
        unique_users = len(set(log.user_id for log in self.logs))
        
        # 操作类型统计
        action_types = {}
        for log in self.logs:
            action = log.action.value
            action_types[action] = action_types.get(action, 0) + 1
        
        # 资源类型统计
        resource_types = {}
        for log in self.logs:
            resource_type = log.resource_type.value
            resource_types[resource_type] = resource_types.get(resource_type, 0) + 1
        
        return {
            "total_logs": total_logs,
            "unique_users": unique_users,
            "action_types": action_types,
            "resource_types": resource_types,
            "oldest_log": self.logs[-1].timestamp.isoformat() if self.logs else None,
            "newest_log": self.logs[0].timestamp.isoformat() if self.logs else None
        }
