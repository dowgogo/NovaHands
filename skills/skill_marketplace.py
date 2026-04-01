"""
技能市场模块

提供技能的发布、搜索、认证、评分和交易功能。
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import json
import os
from datetime import datetime


class SkillTier(Enum):
    """技能等级"""
    BASIC = "basic"
    CERTIFIED = "certified"
    PREMIUM = "premium"


class SkillStatus(Enum):
    """技能状态"""
    DRAFT = "draft"
    PENDING = "pending"
    PUBLISHED = "published"
    CERTIFIED = "certified"
    REJECTED = "rejected"


@dataclass
class SkillMetadata:
    """技能元数据"""
    name: str
    author: str
    description: str
    version: str
    category: str
    tier: SkillTier
    status: SkillStatus
    price: float = 0.0
    downloads: int = 0
    rating: float = 0.0
    rating_count: int = 0
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


class SkillMarketplace:
    """技能市场"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.skills_file = os.path.join(data_dir, "skills.json")
        self.skills: Dict[str, SkillMetadata] = {}
        self._load_skills()
    
    def _load_skills(self):
        """加载技能数据"""
        if os.path.exists(self.skills_file):
            with open(self.skills_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for skill_id, skill_data in data.items():
                    self.skills[skill_id] = SkillMetadata(**skill_data)
    
    def _save_skills(self):
        """保存技能数据"""
        with open(self.skills_file, 'w', encoding='utf-8') as f:
            data = {
                skill_id: {
                    "name": skill.name,
                    "author": skill.author,
                    "description": skill.description,
                    "version": skill.version,
                    "category": skill.category,
                    "tier": skill.tier.value,
                    "status": skill.status.value,
                    "price": skill.price,
                    "downloads": skill.downloads,
                    "rating": skill.rating,
                    "rating_count": skill.rating_count,
                    "created_at": skill.created_at.isoformat(),
                    "updated_at": skill.updated_at.isoformat()
                }
                for skill_id, skill in self.skills.items()
            }
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def publish_skill(
        self,
        skill_id: str,
        name: str,
        author: str,
        description: str,
        version: str,
        category: str,
        price: float = 0.0,
        tier: SkillTier = SkillTier.BASIC
    ) -> SkillMetadata:
        """
        发布技能
        
        Args:
            skill_id: 技能ID
            name: 技能名称
            author: 作者
            description: 描述
            version: 版本
            category: 分类
            price: 价格（0 表示免费）
            tier: 技能等级
            
        Returns:
            技能元数据
        """
        skill = SkillMetadata(
            name=name,
            author=author,
            description=description,
            version=version,
            category=category,
            tier=tier,
            status=SkillStatus.PENDING,
            price=price
        )
        
        self.skills[skill_id] = skill
        self._save_skills()
        
        return skill
    
    def certify_skill(self, skill_id: str, certified: bool, reason: str = ""):
        """
        认证技能
        
        Args:
            skill_id: 技能ID
            certified: 是否认证通过
            reason: 认证原因（拒绝时）
        """
        if skill_id not in self.skills:
            raise ValueError(f"Skill {skill_id} not found")
        
        skill = self.skills[skill_id]
        
        if certified:
            skill.status = SkillStatus.CERTIFIED
            skill.tier = SkillTier.CERTIFIED
        else:
            skill.status = SkillStatus.REJECTED
        
        skill.updated_at = datetime.now()
        self._save_skills()
    
    def rate_skill(self, skill_id: str, rating: int) -> float:
        """
        评价技能
        
        Args:
            skill_id: 技能ID
            rating: 评分（1-5）
            
        Returns:
            更新后的平均评分
        """
        if skill_id not in self.skills:
            raise ValueError(f"Skill {skill_id} not found")
        
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        
        skill = self.skills[skill_id]
        
        # 更新平均评分
        total_rating = skill.rating * skill.rating_count + rating
        skill.rating_count += 1
        skill.rating = total_rating / skill.rating_count
        
        skill.updated_at = datetime.now()
        self._save_skills()
        
        return skill.rating
    
    def record_download(self, skill_id: str):
        """
        记录下载
        
        Args:
            skill_id: 技能ID
        """
        if skill_id in self.skills:
            self.skills[skill_id].downloads += 1
            self._save_skills()
    
    def search_skills(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tier: Optional[SkillTier] = None,
        min_rating: float = 0.0,
        max_price: Optional[float] = None,
        sort_by: str = "downloads"
    ) -> List[Dict]:
        """
        搜索技能
        
        Args:
            query: 搜索关键词
            category: 分类筛选
            tier: 等级筛选
            min_rating: 最低评分
            max_price: 最高价格
            sort_by: 排序方式（downloads, rating, created_at）
            
        Returns:
            技能列表
        """
        results = []
        
        for skill_id, skill in self.skills.items():
            # 状态筛选
            if skill.status not in (SkillStatus.PUBLISHED, SkillStatus.CERTIFIED):
                continue
            
            # 关键词筛选
            if query:
                query_lower = query.lower()
                if (query_lower not in skill.name.lower() and
                    query_lower not in skill.description.lower()):
                    continue
            
            # 分类筛选
            if category and skill.category != category:
                continue
            
            # 等级筛选
            if tier and skill.tier != tier:
                continue
            
            # 评分筛选
            if skill.rating < min_rating:
                continue
            
            # 价格筛选
            if max_price is not None and skill.price > max_price:
                continue
            
            results.append({
                "skill_id": skill_id,
                "name": skill.name,
                "author": skill.author,
                "description": skill.description,
                "version": skill.version,
                "category": skill.category,
                "tier": skill.tier.value,
                "price": skill.price,
                "downloads": skill.downloads,
                "rating": skill.rating,
                "rating_count": skill.rating_count,
                "created_at": skill.created_at
            })
        
        # 排序
        if sort_by == "downloads":
            results.sort(key=lambda x: x["downloads"], reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda x: (x["rating"], x["rating_count"]), reverse=True)
        elif sort_by == "created_at":
            results.sort(key=lambda x: x["created_at"], reverse=True)
        
        return results
    
    def get_leaderboard(self, category: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """
        获取技能排行榜
        
        Args:
            category: 分类（None 表示全部）
            limit: 返回数量
            
        Returns:
            技能列表（按下载量降序）
        """
        skills = self.search_skills(category=category, sort_by="downloads")
        return skills[:limit]
    
    def get_contributor_stats(self, author: str) -> Dict:
        """
        获取贡献者统计
        
        Args:
            author: 作者名称
            
        Returns:
            统计信息
        """
        skills = [
            skill for skill in self.skills.values()
            if skill.author == author
        ]
        
        return {
            "total_skills": len(skills),
            "total_downloads": sum(s.downloads for s in skills),
            "average_rating": sum(s.rating * s.rating_count for s in skills) / 
                            max(1, sum(s.rating_count for s in skills)),
            "total_revenue": sum(s.price * s.downloads for s in skills),
            "skills": [
                {
                    "skill_id": skill_id,
                    "name": skill.name,
                    "downloads": skill.downloads,
                    "rating": skill.rating,
                    "revenue": skill.price * skill.downloads
                }
                for skill_id, skill in self.skills.items()
                if skill.author == author
            ]
        }


class RevenueShareCalculator:
    """收益分成计算器"""
    
    DEVELOPER_SHARE = 0.7  # 开发者分成 70%
    PLATFORM_SHARE = 0.3   # 平台分成 30%
    REFERRAL_BONUS = 0.05  # 推荐人奖励 +5%（从平台分成中扣除）
    
    @staticmethod
    def calculate(
        sale_price: float,
        quantity: int = 1,
        has_referrer: bool = False
    ) -> Dict[str, float]:
        """
        计算收益分成
        
        Args:
            sale_price: 销售价格
            quantity: 销售数量
            has_referrer: 是否有推荐人
            
        Returns:
            分成明细
        """
        total_revenue = sale_price * quantity
        
        if has_referrer:
            # 有推荐人：开发者 70%，推荐人 5%，平台 25%
            developer_share = total_revenue * RevenueShareCalculator.DEVELOPER_SHARE
            referrer_share = total_revenue * RevenueShareCalculator.REFERRAL_BONUS
            platform_share = total_revenue * (1 - RevenueShareCalculator.DEVELOPER_SHARE - RevenueShareCalculator.REFERRAL_BONUS)
        else:
            # 无推荐人：开发者 70%，平台 30%
            developer_share = total_revenue * RevenueShareCalculator.DEVELOPER_SHARE
            referrer_share = 0.0
            platform_share = total_revenue * RevenueShareCalculator.PLATFORM_SHARE
        
        return {
            "total_revenue": total_revenue,
            "developer_share": developer_share,
            "referrer_share": referrer_share,
            "platform_share": platform_share
        }
