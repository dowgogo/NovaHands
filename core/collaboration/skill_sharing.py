"""
技能共享模块

提供技能可见性控制、团队技能库、版本管理等功能。
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set
from enum import Enum


class SkillVisibility(Enum):
    """技能可见性"""
    PRIVATE = "private"  # 私人（仅创建者）
    TEAM = "team"        # 团队（团队成员）
    PUBLIC = "public"    # 公开（所有用户，技能市场）


class SkillVersion:
    """技能版本"""
    
    def __init__(
        self,
        version: str,
        author_id: str,
        author_name: str,
        changes: str = ""
    ):
        self.version = version
        self.author_id = author_id
        self.author_name = author_name
        self.changes = changes
        self.created_at = datetime.now()
        self.is_published = False
        self.download_count = 0
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "version": self.version,
            "author_id": self.author_id,
            "author_name": self.author_name,
            "changes": self.changes,
            "created_at": self.created_at.isoformat(),
            "is_published": self.is_published,
            "download_count": self.download_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SkillVersion":
        """从字典创建版本"""
        version = cls(
            version=data["version"],
            author_id=data["author_id"],
            author_name=data["author_name"],
            changes=data.get("changes", "")
        )
        version.created_at = datetime.fromisoformat(data["created_at"])
        version.is_published = data.get("is_published", False)
        version.download_count = data.get("download_count", 0)
        return version


class SharedSkill:
    """共享技能"""
    
    def __init__(
        self,
        name: str,
        owner_id: str,
        owner_name: str,
        visibility: SkillVisibility = SkillVisibility.PRIVATE,
        team_id: Optional[str] = None,
        skill_id: Optional[str] = None
    ):
        self.skill_id = skill_id or str(uuid.uuid4())
        self.name = name
        self.owner_id = owner_id
        self.owner_name = owner_name
        self.visibility = visibility
        self.team_id = team_id
        self.versions: List[SkillVersion] = []
        self.current_version = "1.0.0"
        self.collaborators: Set[str] = set()  # 协作者 ID 集合
        self.tags: List[str] = []
        self.description = ""
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def add_version(
        self,
        version: str,
        author_id: str,
        author_name: str,
        changes: str = ""
    ) -> SkillVersion:
        """添加版本"""
        # 检查版本号是否已存在
        for v in self.versions:
            if v.version == version:
                raise ValueError(f"版本 {version} 已存在")
        
        skill_version = SkillVersion(version, author_id, author_name, changes)
        self.versions.append(skill_version)
        self.current_version = version
        self.updated_at = datetime.now()
        
        return skill_version
    
    def publish_version(self, version: str):
        """发布版本"""
        for v in self.versions:
            if v.version == version:
                v.is_published = True
                self.updated_at = datetime.now()
                return
        
        raise ValueError(f"版本 {version} 不存在")
    
    def add_collaborator(self, user_id: str):
        """添加协作者"""
        if user_id == self.owner_id:
            raise ValueError("不能将所有者添加为协作者")
        
        self.collaborators.add(user_id)
    
    def remove_collaborator(self, user_id: str):
        """移除协作者"""
        self.collaborators.discard(user_id)
    
    def is_visible_to(self, user_id: str, team_ids: List[str]) -> bool:
        """检查技能对用户是否可见"""
        # 私人技能：仅所有者和协作者可见
        if self.visibility == SkillVisibility.PRIVATE:
            return user_id == self.owner_id or user_id in self.collaborators
        
        # 团队技能：团队成员可见
        if self.visibility == SkillVisibility.TEAM:
            return self.team_id in team_ids
        
        # 公开技能：所有用户可见
        return True
    
    def can_edit(self, user_id: str) -> bool:
        """检查用户是否可以编辑技能"""
        return user_id == self.owner_id or user_id in self.collaborators
    
    def get_contributors(self) -> List[Dict]:
        """获取贡献者列表"""
        contributors = {
            self.owner_id: {
                "user_id": self.owner_id,
                "user_name": self.owner_name,
                "role": "owner",
                "contributions": len([v for v in self.versions if v.author_id == self.owner_id])
            }
        }
        
        # 添加协作者
        for user_id in self.collaborators:
            if user_id not in contributors:
                # 这里需要从用户管理器获取用户名
                contributors[user_id] = {
                    "user_id": user_id,
                    "user_name": "",  # 需要从用户管理器获取
                    "role": "collaborator",
                    "contributions": len([v for v in self.versions if v.author_id == user_id])
                }
            else:
                contributors[user_id]["role"] = "collaborator"
        
        return list(contributors.values())
    
    def to_dict(self, include_private: bool = False) -> Dict:
        """转换为字典"""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "owner_id": self.owner_id,
            "owner_name": self.owner_name,
            "visibility": self.visibility.value,
            "team_id": self.team_id,
            "current_version": self.current_version,
            "collaborators": list(self.collaborators) if include_private else [],
            "tags": self.tags,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "versions": [v.to_dict() for v in self.versions] if include_private else []
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "SharedSkill":
        """从字典创建技能"""
        skill = cls(
            name=data["name"],
            owner_id=data["owner_id"],
            owner_name=data["owner_name"],
            visibility=SkillVisibility(data["visibility"]),
            team_id=data.get("team_id"),
            skill_id=data["skill_id"]
        )
        skill.created_at = datetime.fromisoformat(data["created_at"])
        skill.updated_at = datetime.fromisoformat(data["updated_at"])
        skill.tags = data.get("tags", [])
        skill.description = data.get("description", "")
        
        # 重建版本列表
        if "versions" in data:
            skill.versions = [SkillVersion.from_dict(v) for v in data["versions"]]
        
        # 重建协作者集合
        if "collaborators" in data:
            skill.collaborators = set(data["collaborators"])
        
        return skill


class SkillSharingManager:
    """技能共享管理器"""
    
    def __init__(self, user_manager=None, team_manager=None):
        self.user_manager = user_manager
        self.team_manager = team_manager
        self.skills: Dict[str, SharedSkill] = {}
        self.user_skills: Dict[str, Set[str]] = {}  # user_id -> skill_ids
        self.team_skills: Dict[str, Set[str]] = {}  # team_id -> skill_ids
    
    def create_skill(
        self,
        owner_id: str,
        owner_name: str,
        name: str,
        visibility: SkillVisibility = SkillVisibility.PRIVATE,
        team_id: Optional[str] = None,
        description: str = "",
        tags: List[str] = None
    ) -> SharedSkill:
        """创建技能"""
        skill = SharedSkill(
            name=name,
            owner_id=owner_id,
            owner_name=owner_name,
            visibility=visibility,
            team_id=team_id
        )
        skill.description = description
        if tags:
            skill.tags = tags
        
        # 添加初始版本
        skill.add_version("1.0.0", owner_id, owner_name, "初始版本")
        
        # 保存技能
        self.skills[skill.skill_id] = skill
        
        # 更新索引
        if owner_id not in self.user_skills:
            self.user_skills[owner_id] = set()
        self.user_skills[owner_id].add(skill.skill_id)
        
        if team_id:
            if team_id not in self.team_skills:
                self.team_skills[team_id] = set()
            self.team_skills[team_id].add(skill.skill_id)
        
        return skill
    
    def get_skill(self, skill_id: str, user_id: Optional[str] = None) -> Optional[SharedSkill]:
        """获取技能"""
        skill = self.skills.get(skill_id)
        
        if skill and user_id:
            # 获取用户的团队 ID 列表
            team_ids = []
            if self.team_manager and self.user_manager:
                teams = self.team_manager.get_user_teams(user_id)
                team_ids = [t.team_id for t in teams]
            
            # 检查可见性
            if not skill.is_visible_to(user_id, team_ids):
                return None
        
        return skill
    
    def get_user_skills(self, user_id: str, visibility: Optional[SkillVisibility] = None) -> List[SharedSkill]:
        """获取用户的技能"""
        skill_ids = self.user_skills.get(user_id, set())
        skills = [self.skills[sid] for sid in skill_ids if sid in self.skills]
        
        if visibility:
            skills = [s for s in skills if s.visibility == visibility]
        
        return skills
    
    def get_team_skills(self, team_id: str, user_id: Optional[str] = None) -> List[SharedSkill]:
        """获取团队技能"""
        skill_ids = self.team_skills.get(team_id, set())
        skills = [self.skills[sid] for sid in skill_ids if sid in self.skills]
        
        # 如果指定了用户，过滤可见性
        if user_id:
            team_ids = []
            if self.team_manager:
                teams = self.team_manager.get_user_teams(user_id)
                team_ids = [t.team_id for t in teams]
            
            skills = [s for s in skills if s.is_visible_to(user_id, team_ids)]
        
        return skills
    
    def search_skills(
        self,
        user_id: str,
        keyword: str = "",
        tags: List[str] = None,
        visibility: Optional[SkillVisibility] = None
    ) -> List[SharedSkill]:
        """搜索技能"""
        # 获取用户的团队 ID 列表
        team_ids = []
        if self.team_manager:
            teams = self.team_manager.get_user_teams(user_id)
            team_ids = [t.team_id for t in teams]
        
        # 过滤可见技能
        skills = [
            s for s in self.skills.values()
            if s.is_visible_to(user_id, team_ids)
        ]
        
        # 关键词搜索
        if keyword:
            keyword = keyword.lower()
            skills = [
                s for s in skills
                if keyword in s.name.lower() or keyword in s.description.lower()
            ]
        
        # 标签过滤
        if tags:
            skills = [
                s for s in skills
                if any(tag in s.tags for tag in tags)
            ]
        
        # 可见性过滤
        if visibility:
            skills = [s for s in skills if s.visibility == visibility]
        
        return skills
    
    def update_skill_visibility(
        self,
        skill_id: str,
        user_id: str,
        visibility: SkillVisibility,
        team_id: Optional[str] = None
    ):
        """更新技能可见性"""
        skill = self.skills.get(skill_id)
        if not skill:
            raise ValueError(f"技能 {skill_id} 不存在")
        
        if skill.owner_id != user_id:
            raise ValueError("只有技能所有者可以修改可见性")
        
        # 更新旧索引
        if skill.team_id:
            if skill.team_id in self.team_skills:
                self.team_skills[skill.team_id].discard(skill_id)
        
        # 更新可见性
        skill.visibility = visibility
        skill.team_id = team_id
        
        # 更新新索引
        if team_id and visibility == SkillVisibility.TEAM:
            if team_id not in self.team_skills:
                self.team_skills[team_id] = set()
            self.team_skills[team_id].add(skill_id)
    
    def add_collaborator(
        self,
        skill_id: str,
        owner_id: str,
        collaborator_id: str
    ):
        """添加协作者"""
        skill = self.skills.get(skill_id)
        if not skill:
            raise ValueError(f"技能 {skill_id} 不存在")
        
        if skill.owner_id != owner_id:
            raise ValueError("只有技能所有者可以添加协作者")
        
        skill.add_collaborator(collaborator_id)
    
    def remove_collaborator(
        self,
        skill_id: str,
        owner_id: str,
        collaborator_id: str
    ):
        """移除协作者"""
        skill = self.skills.get(skill_id)
        if not skill:
            raise ValueError(f"技能 {skill_id} 不存在")
        
        if skill.owner_id != owner_id:
            raise ValueError("只有技能所有者可以移除协作者")
        
        skill.remove_collaborator(collaborator_id)
    
    def add_skill_version(
        self,
        skill_id: str,
        user_id: str,
        user_name: str,
        version: str,
        changes: str = ""
    ) -> SkillVersion:
        """添加技能版本"""
        skill = self.skills.get(skill_id)
        if not skill:
            raise ValueError(f"技能 {skill_id} 不存在")
        
        if not skill.can_edit(user_id):
            raise ValueError("无权限编辑此技能")
        
        return skill.add_version(version, user_id, user_name, changes)
    
    def delete_skill(self, skill_id: str, user_id: str):
        """删除技能"""
        skill = self.skills.get(skill_id)
        if not skill:
            raise ValueError(f"技能 {skill_id} 不存在")
        
        if skill.owner_id != user_id:
            raise ValueError("只有技能所有者可以删除技能")
        
        # 删除索引
        if skill.owner_id in self.user_skills:
            self.user_skills[skill.owner_id].discard(skill_id)
        
        if skill.team_id and skill.team_id in self.team_skills:
            self.team_skills[skill.team_id].discard(skill_id)
        
        # 删除技能
        del self.skills[skill_id]
