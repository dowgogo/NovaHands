"""
任务协作模块

提供任务管理、分配、跟踪、工作流编辑等功能。
"""

import uuid
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


class TaskStatus(Enum):
    """任务状态"""
    DRAFT = "draft"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    COMPLETED = "completed"
    ON_HOLD = "on_hold"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """任务优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(Enum):
    """任务类型"""
    PERSONAL = "personal"
    TEAM = "team"
    WORKFLOW = "workflow"


class WorkflowStep:
    """工作流步骤"""
    
    def __init__(
        self,
        name: str,
        skill_id: str,
        parameters: Dict,
        order: int
    ):
        self.step_id = str(uuid.uuid4())
        self.name = name
        self.skill_id = skill_id
        self.parameters = parameters
        self.order = order
        self.status = TaskStatus.DRAFT
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "step_id": self.step_id,
            "name": self.name,
            "skill_id": self.skill_id,
            "parameters": self.parameters,
            "order": self.order,
            "status": self.status.value,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "WorkflowStep":
        """从字典创建步骤"""
        step = cls(
            name=data["name"],
            skill_id=data["skill_id"],
            parameters=data["parameters"],
            order=data["order"]
        )
        step.step_id = data["step_id"]
        step.status = TaskStatus(data["status"])
        step.started_at = datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
        step.completed_at = datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None
        return step


class TaskComment:
    """任务评论"""
    
    def __init__(self, user_id: str, user_name: str, content: str):
        self.comment_id = str(uuid.uuid4())
        self.user_id = user_id
        self.user_name = user_name
        self.content = content
        self.created_at = datetime.now()
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "comment_id": self.comment_id,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "content": self.content,
            "created_at": self.created_at.isoformat()
        }


class Task:
    """任务类"""
    
    def __init__(
        self,
        name: str,
        owner_id: str,
        owner_name: str,
        description: str = "",
        task_type: TaskType = TaskType.PERSONAL,
        team_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: Optional[datetime] = None,
        task_id: Optional[str] = None
    ):
        self.task_id = task_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.type = task_type
        self.owner_id = owner_id
        self.owner_name = owner_name
        self.assignee_id: Optional[str] = None
        self.assignee_name: Optional[str] = None
        self.team_id = team_id
        self.status = TaskStatus.DRAFT
        self.priority = priority
        self.workflow: List[WorkflowStep] = []
        self.comments: List[TaskComment] = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.due_date = due_date
    
    def assign(self, user_id: str, user_name: str):
        """分配任务"""
        if self.status not in [TaskStatus.DRAFT, TaskStatus.ASSIGNED, TaskStatus.ON_HOLD]:
            raise ValueError(f"当前状态 {self.status.value} 下无法分配任务")
        
        self.assignee_id = user_id
        self.assignee_name = user_name
        self.status = TaskStatus.ASSIGNED
        self.updated_at = datetime.now()
    
    def start(self, user_id: str):
        """开始任务"""
        if self.assignee_id != user_id:
            raise ValueError("只有被分配人可以开始任务")
        
        if self.status != TaskStatus.ASSIGNED:
            raise ValueError(f"当前状态 {self.status.value} 下无法开始任务")
        
        self.status = TaskStatus.IN_PROGRESS
        self.updated_at = datetime.now()
    
    def complete(self, user_id: str):
        """完成任务"""
        if self.assignee_id != user_id:
            raise ValueError("只有被分配人可以完成任务")
        
        if self.status != TaskStatus.IN_PROGRESS:
            raise ValueError(f"当前状态 {self.status.value} 下无法完成任务")
        
        self.status = TaskStatus.COMPLETED
        self.updated_at = datetime.now()
    
    def update_status(self, user_id: str, status: TaskStatus):
        """更新状态"""
        # 权限检查
        if self.owner_id != user_id and self.assignee_id != user_id:
            raise ValueError("只有任务所有者或被分配人可以更新状态")
        
        # 状态转换验证
        valid_transitions = {
            TaskStatus.DRAFT: [TaskStatus.ASSIGNED, TaskStatus.CANCELLED],
            TaskStatus.ASSIGNED: [TaskStatus.IN_PROGRESS, TaskStatus.ON_HOLD, TaskStatus.CANCELLED],
            TaskStatus.IN_PROGRESS: [TaskStatus.REVIEW, TaskStatus.COMPLETED, TaskStatus.ON_HOLD, TaskStatus.CANCELLED],
            TaskStatus.REVIEW: [TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED, TaskStatus.ON_HOLD],
            TaskStatus.ON_HOLD: [TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED],
            TaskStatus.COMPLETED: [],
            TaskStatus.CANCELLED: [],
        }
        
        if status not in valid_transitions.get(self.status, []):
            raise ValueError(f"无法从 {self.status.value} 转换到 {status.value}")
        
        self.status = status
        self.updated_at = datetime.now()
    
    def add_workflow_step(self, name: str, skill_id: str, parameters: Dict) -> WorkflowStep:
        """添加工作流步骤"""
        order = len(self.workflow) + 1
        step = WorkflowStep(name, skill_id, parameters, order)
        self.workflow.append(step)
        self.updated_at = datetime.now()
        return step
    
    def remove_workflow_step(self, step_id: str):
        """移除工作流步骤"""
        self.workflow = [s for s in self.workflow if s.step_id != step_id]
        # 重新排序
        for i, step in enumerate(self.workflow, 1):
            step.order = i
        self.updated_at = datetime.now()
    
    def update_workflow_step(self, step_id: str, **kwargs):
        """更新工作流步骤"""
        for step in self.workflow:
            if step.step_id == step_id:
                for key, value in kwargs.items():
                    if hasattr(step, key):
                        setattr(step, key, value)
                self.updated_at = datetime.now()
                return
        
        raise ValueError(f"步骤 {step_id} 不存在")
    
    def add_comment(self, user_id: str, user_name: str, content: str) -> TaskComment:
        """添加评论"""
        comment = TaskComment(user_id, user_name, content)
        self.comments.append(comment)
        self.updated_at = datetime.now()
        return comment
    
    def is_accessible_by(self, user_id: str) -> bool:
        """检查用户是否可以访问任务"""
        if self.type == TaskType.PERSONAL:
            return self.owner_id == user_id or self.assignee_id == user_id
        else:
            # 团队任务：所有团队成员都可以查看
            # 这里需要从团队管理器获取成员列表
            # 暂时简化为：团队成员都可以访问
            return True
    
    def can_edit(self, user_id: str) -> bool:
        """检查用户是否可以编辑任务"""
        return self.owner_id == user_id or self.assignee_id == user_id
    
    def to_dict(self, include_private: bool = False) -> Dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "type": self.type.value,
            "owner_id": self.owner_id,
            "owner_name": self.owner_name,
            "assignee_id": self.assignee_id,
            "assignee_name": self.assignee_name,
            "team_id": self.team_id,
            "status": self.status.value,
            "priority": self.priority.value,
            "workflow": [s.to_dict() for s in self.workflow],
            "comments": [c.to_dict() for c in self.comments],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "due_date": self.due_date.isoformat() if self.due_date else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        """从字典创建任务"""
        task = cls(
            name=data["name"],
            owner_id=data["owner_id"],
            owner_name=data["owner_name"],
            description=data.get("description", ""),
            task_type=TaskType(data["type"]),
            team_id=data.get("team_id"),
            priority=TaskPriority(data["priority"]),
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            task_id=data["task_id"]
        )
        task.status = TaskStatus(data["status"])
        task.assignee_id = data.get("assignee_id")
        task.assignee_name = data.get("assignee_name")
        task.created_at = datetime.fromisoformat(data["created_at"])
        task.updated_at = datetime.fromisoformat(data["updated_at"])
        
        # 重建工作流
        if "workflow" in data:
            task.workflow = [WorkflowStep.from_dict(s) for s in data["workflow"]]
        
        # 重建评论
        if "comments" in data:
            for comment_data in data["comments"]:
                comment = TaskComment(
                    user_id=comment_data["user_id"],
                    user_name=comment_data["user_name"],
                    content=comment_data["content"]
                )
                comment.comment_id = comment_data["comment_id"]
                comment.created_at = datetime.fromisoformat(comment_data["created_at"])
                task.comments.append(comment)
        
        return task


class TaskManager:
    """任务管理器"""
    
    def __init__(self, user_manager=None, team_manager=None):
        self.user_manager = user_manager
        self.team_manager = team_manager
        self.tasks: Dict[str, Task] = {}
        self.user_tasks: Dict[str, Set[str]] = {}  # user_id -> task_ids
        self.team_tasks: Dict[str, Set[str]] = {}  # team_id -> task_ids
    
    def create_task(
        self,
        name: str,
        owner_id: str,
        owner_name: str,
        description: str = "",
        task_type: TaskType = TaskType.PERSONAL,
        team_id: Optional[str] = None,
        priority: TaskPriority = TaskPriority.MEDIUM,
        due_date: Optional[datetime] = None
    ) -> Task:
        """创建任务"""
        task = Task(
            name=name,
            owner_id=owner_id,
            owner_name=owner_name,
            description=description,
            task_type=task_type,
            team_id=team_id,
            priority=priority,
            due_date=due_date
        )
        
        # 保存任务
        self.tasks[task.task_id] = task
        
        # 更新索引
        if owner_id not in self.user_tasks:
            self.user_tasks[owner_id] = set()
        self.user_tasks[owner_id].add(task.task_id)
        
        if team_id:
            if team_id not in self.team_tasks:
                self.team_tasks[team_id] = set()
            self.team_tasks[team_id].add(task.task_id)
        
        return task
    
    def get_task(self, task_id: str, user_id: Optional[str] = None) -> Optional[Task]:
        """获取任务"""
        task = self.tasks.get(task_id)
        
        if task and user_id:
            # 检查访问权限
            if not task.is_accessible_by(user_id):
                return None
        
        return task
    
    def get_user_tasks(
        self,
        user_id: str,
        status: Optional[TaskStatus] = None
    ) -> List[Task]:
        """获取用户的任务（创建的或被分配的）"""
        # 获取用户创建的任务
        task_ids = self.user_tasks.get(user_id, set())
        
        # 添加用户被分配的任务
        all_tasks = list(self.tasks.values())
        for task in all_tasks:
            if task.assignee_id == user_id and task.task_id not in task_ids:
                task_ids.add(task.task_id)
        
        tasks = [self.tasks[tid] for tid in task_ids if tid in self.tasks]
        
        # 状态过滤
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        return tasks
    
    def get_team_tasks(
        self,
        team_id: str,
        status: Optional[TaskStatus] = None
    ) -> List[Task]:
        """获取团队任务"""
        task_ids = self.team_tasks.get(team_id, set())
        tasks = [self.tasks[tid] for tid in task_ids if tid in self.tasks]
        
        # 状态过滤
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        return tasks
    
    def assign_task(
        self,
        task_id: str,
        assignee_id: str,
        assignee_name: str,
        operator_id: str
    ):
        """分配任务"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        # 权限检查
        if task.owner_id != operator_id:
            raise ValueError("只有任务所有者可以分配任务")
        
        task.assign(assignee_id, assignee_name)
        
        # 更新用户索引
        if assignee_id not in self.user_tasks:
            self.user_tasks[assignee_id] = set()
        self.user_tasks[assignee_id].add(task_id)
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        user_id: str
    ):
        """更新任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        task.update_status(user_id, status)
    
    def add_task_comment(
        self,
        task_id: str,
        user_id: str,
        user_name: str,
        content: str
    ) -> TaskComment:
        """添加任务评论"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        return task.add_comment(user_id, user_name, content)
    
    def delete_task(self, task_id: str, user_id: str):
        """删除任务"""
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"任务 {task_id} 不存在")
        
        if task.owner_id != user_id:
            raise ValueError("只有任务所有者可以删除任务")
        
        # 删除索引
        if task.owner_id in self.user_tasks:
            self.user_tasks[task.owner_id].discard(task_id)
        
        if task.assignee_id and task.assignee_id in self.user_tasks:
            self.user_tasks[task.assignee_id].discard(task_id)
        
        if task.team_id and task.team_id in self.team_tasks:
            self.team_tasks[task.team_id].discard(task_id)
        
        # 删除任务
        del self.tasks[task_id]
    
    def search_tasks(
        self,
        user_id: str,
        keyword: str = "",
        status: Optional[TaskStatus] = None,
        priority: Optional[TaskPriority] = None
    ) -> List[Task]:
        """搜索任务"""
        # 获取用户可访问的任务
        tasks = self.get_user_tasks(user_id)
        
        # 关键词搜索
        if keyword:
            keyword = keyword.lower()
            tasks = [
                t for t in tasks
                if keyword in t.name.lower() or keyword in t.description.lower()
            ]
        
        # 状态过滤
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # 优先级过滤
        if priority:
            tasks = [t for t in tasks if t.priority == priority]
        
        return tasks
