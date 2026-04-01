"""
用户与团队管理模块

提供用户注册、认证、团队创建、成员管理等功能。
"""

import uuid
from datetime import datetime
from typing import List, Dict, Optional
from enum import Enum


class UserRole(Enum):
    """用户角色"""
    OWNER = "owner"       # 所有者
    ADMIN = "admin"       # 管理员
    MEMBER = "member"     # 成员
    VIEWER = "viewer"     # 查看者


class TeamPlan(Enum):
    """团队套餐"""
    FREE = "free"         # 免费版（最多 5 人）
    PRO = "pro"           # 专业版（最多 20 人）
    ENTERPRISE = "enterprise"  # 企业版（无限人数）


class User:
    """用户类"""
    
    def __init__(
        self,
        username: str,
        email: str,
        password_hash: str,
        user_id: Optional[str] = None
    ):
        self.user_id = user_id or str(uuid.uuid4())
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = UserRole.MEMBER
        self.created_at = datetime.now()
        self.last_active = datetime.now()
        self.preferences = {
            "theme": "dark",
            "language": "zh-CN",
            "notification": True
        }
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "preferences": self.preferences
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "User":
        """从字典创建用户"""
        user = cls(
            username=data["username"],
            email=data["email"],
            password_hash=data["password_hash"],
            user_id=data["user_id"]
        )
        user.role = UserRole(data["role"])
        user.created_at = datetime.fromisoformat(data["created_at"])
        user.last_active = datetime.fromisoformat(data["last_active"])
        user.preferences = data["preferences"]
        return user


class TeamMember:
    """团队成员类"""
    
    def __init__(
        self,
        user_id: str,
        username: str,
        role: UserRole = UserRole.MEMBER
    ):
        self.user_id = user_id
        self.username = username
        self.role = role
        self.joined_at = datetime.now()
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "role": self.role.value,
            "joined_at": self.joined_at.isoformat()
        }


class Team:
    """团队类"""
    
    def __init__(
        self,
        team_name: str,
        owner_id: str,
        owner_name: str,
        description: str = "",
        plan: TeamPlan = TeamPlan.FREE,
        team_id: Optional[str] = None
    ):
        self.team_id = team_id or str(uuid.uuid4())
        self.team_name = team_name
        self.description = description
        self.owner_id = owner_id
        self.members = [
            TeamMember(owner_id, owner_name, UserRole.OWNER)
        ]
        self.plan = plan
        self.settings = {
            "skill_sharing": True,
            "task_collaboration": True,
            "default_permissions": ["read", "update"]
        }
        self.created_at = datetime.now()
    
    def add_member(self, user_id: str, username: str, role: UserRole = UserRole.MEMBER):
        """添加成员"""
        # 检查成员是否存在
        for member in self.members:
            if member.user_id == user_id:
                raise ValueError(f"用户 {username} 已在团队中")
        
        # 检查人数限制
        max_members = {
            TeamPlan.FREE: 5,
            TeamPlan.PRO: 20,
            TeamPlan.ENTERPRISE: float("inf")
        }
        if len(self.members) >= max_members[self.plan]:
            raise ValueError(f"{self.plan.value} 套餐最多支持 {max_members[self.plan]} 人")
        
        self.members.append(TeamMember(user_id, username, role))
    
    def remove_member(self, user_id: str):
        """移除成员"""
        if user_id == self.owner_id:
            raise ValueError("不能移除团队所有者")
        
        self.members = [m for m in self.members if m.user_id != user_id]
    
    def update_member_role(self, user_id: str, role: UserRole):
        """更新成员角色"""
        if user_id == self.owner_id:
            raise ValueError("不能修改所有者的角色")
        
        for member in self.members:
            if member.user_id == user_id:
                member.role = role
                return
        
        raise ValueError(f"用户 {user_id} 不在团队中")
    
    def get_member(self, user_id: str) -> Optional[TeamMember]:
        """获取成员"""
        for member in self.members:
            if member.user_id == user_id:
                return member
        return None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "team_id": self.team_id,
            "team_name": self.team_name,
            "description": self.description,
            "owner_id": self.owner_id,
            "members": [m.to_dict() for m in self.members],
            "plan": self.plan.value,
            "settings": self.settings,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Team":
        """从字典创建团队"""
        team = cls(
            team_name=data["team_name"],
            owner_id=data["owner_id"],
            owner_name="",  # 需要从 members 中获取
            description=data.get("description", ""),
            plan=TeamPlan(data["plan"]),
            team_id=data["team_id"]
        )
        team.created_at = datetime.fromisoformat(data["created_at"])
        team.settings = data["settings"]
        
        # 重建成员列表
        team.members = []
        for member_data in data["members"]:
            member = TeamMember(
                user_id=member_data["user_id"],
                username=member_data["username"],
                role=UserRole(member_data["role"])
            )
            member.joined_at = datetime.fromisoformat(member_data["joined_at"])
            team.members.append(member)
        
        return team


class UserManager:
    """用户管理器"""
    
    def __init__(self):
        self.users: Dict[str, User] = {}
        self.email_index: Dict[str, str] = {}
        self.username_index: Dict[str, str] = {}
    
    def register(
        self,
        username: str,
        email: str,
        password_hash: str
    ) -> User:
        """注册用户"""
        # 检查用户名和邮箱是否已存在
        if email in self.email_index:
            raise ValueError(f"邮箱 {email} 已被注册")
        if username in self.username_index:
            raise ValueError(f"用户名 {username} 已被使用")
        
        user = User(username, email, password_hash)
        self.users[user.user_id] = user
        self.email_index[email] = user.user_id
        self.username_index[username] = user.user_id
        
        return user
    
    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
        return self.users.get(user_id)
    
    def get_user_by_email(self, email: str) -> Optional[User]:
        """通过邮箱获取用户"""
        user_id = self.email_index.get(email)
        return self.users.get(user_id) if user_id else None
    
    def update_user(self, user_id: str, **kwargs):
        """更新用户信息"""
        user = self.users.get(user_id)
        if not user:
            raise ValueError(f"用户 {user_id} 不存在")
        
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        
        user.last_active = datetime.now()
    
    def delete_user(self, user_id: str):
        """删除用户"""
        if user_id not in self.users:
            raise ValueError(f"用户 {user_id} 不存在")
        
        user = self.users[user_id]
        del self.email_index[user.email]
        del self.username_index[user.username]
        del self.users[user_id]


class TeamManager:
    """团队管理器"""
    
    def __init__(self, user_manager: UserManager):
        self.user_manager = user_manager
        self.teams: Dict[str, Team] = {}
        self.user_teams: Dict[str, List[str]] = {}  # user_id -> team_ids
    
    def create_team(
        self,
        owner_id: str,
        team_name: str,
        description: str = "",
        plan: TeamPlan = TeamPlan.FREE
    ) -> Team:
        """创建团队"""
        owner = self.user_manager.get_user(owner_id)
        if not owner:
            raise ValueError(f"用户 {owner_id} 不存在")
        
        team = Team(
            team_name=team_name,
            owner_id=owner_id,
            owner_name=owner.username,
            description=description,
            plan=plan
        )
        
        self.teams[team.team_id] = team
        
        # 更新用户团队索引
        if owner_id not in self.user_teams:
            self.user_teams[owner_id] = []
        self.user_teams[owner_id].append(team.team_id)
        
        return team
    
    def get_team(self, team_id: str) -> Optional[Team]:
        """获取团队"""
        return self.teams.get(team_id)
    
    def get_user_teams(self, user_id: str) -> List[Team]:
        """获取用户所属的团队"""
        team_ids = self.user_teams.get(user_id, [])
        return [self.teams[tid] for tid in team_ids if tid in self.teams]
    
    def invite_member(
        self,
        team_id: str,
        inviter_id: str,
        user_id: str,
        role: UserRole = UserRole.MEMBER
    ):
        """邀请成员"""
        team = self.teams.get(team_id)
        if not team:
            raise ValueError(f"团队 {team_id} 不存在")
        
        # 检查邀请人权限（只有 owner 和 admin 可以邀请）
        inviter = team.get_member(inviter_id)
        if not inviter or inviter.role not in [UserRole.OWNER, UserRole.ADMIN]:
            raise ValueError("无权限邀请成员")
        
        user = self.user_manager.get_user(user_id)
        if not user:
            raise ValueError(f"用户 {user_id} 不存在")
        
        team.add_member(user_id, user.username, role)
        
        # 更新用户团队索引
        if user_id not in self.user_teams:
            self.user_teams[user_id] = []
        self.user_teams[user_id].append(team_id)
    
    def remove_member(
        self,
        team_id: str,
        operator_id: str,
        user_id: str
    ):
        """移除成员"""
        team = self.teams.get(team_id)
        if not team:
            raise ValueError(f"团队 {team_id} 不存在")
        
        # 检查操作人权限（只有 owner 和 admin 可以移除）
        operator = team.get_member(operator_id)
        if not operator or operator.role not in [UserRole.OWNER, UserRole.ADMIN]:
            raise ValueError("无权限移除成员")
        
        team.remove_member(user_id)
        
        # 更新用户团队索引
        if user_id in self.user_teams:
            self.user_teams[user_id] = [
                tid for tid in self.user_teams[user_id] if tid != team_id
            ]
    
    def update_member_role(
        self,
        team_id: str,
        operator_id: str,
        user_id: str,
        role: UserRole
    ):
        """更新成员角色"""
        team = self.teams.get(team_id)
        if not team:
            raise ValueError(f"团队 {team_id} 不存在")
        
        # 检查操作人权限（只有 owner 可以修改角色）
        operator = team.get_member(operator_id)
        if not operator or operator.role != UserRole.OWNER:
            raise ValueError("只有团队所有者可以修改成员角色")
        
        team.update_member_role(user_id, role)
    
    def delete_team(self, team_id: str, operator_id: str):
        """删除团队"""
        team = self.teams.get(team_id)
        if not team:
            raise ValueError(f"团队 {team_id} 不存在")
        
        # 只有所有者可以删除团队
        if team.owner_id != operator_id:
            raise ValueError("只有团队所有者可以删除团队")
        
        # 从用户团队索引中移除
        for member in team.members:
            if member.user_id in self.user_teams:
                self.user_teams[member.user_id] = [
                    tid for tid in self.user_teams[member.user_id] if tid != team_id
                ]
        
        del self.teams[team_id]
