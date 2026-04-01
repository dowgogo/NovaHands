# NovaHands 协作系统设计文档

## 设计目标

为 NovaHands 智能桌面助手添加企业级协作功能，支持团队共享技能、多用户协作任务、权限管理和实时协作编辑。

---

## 核心功能模块

### 1. 用户与团队管理 (`core/collaboration/user_manager.py`)

#### 1.1 用户系统
- **用户类型**
  - 个人用户（免费/Pro）
  - 企业用户（企业版）
  
- **用户属性**
  ```python
  {
    "user_id": "uuid",
    "username": "string",
    "email": "string",
    "role": "owner|admin|member|viewer",
    "permissions": ["list"],
    "created_at": "datetime",
    "last_active": "datetime",
    "preferences": {
      "theme": "dark|light",
      "language": "zh-CN|en-US",
      "notification": bool
    }
  }
  ```

#### 1.2 团队系统
- **团队结构**
  ```python
  {
    "team_id": "uuid",
    "team_name": "string",
    "description": "string",
    "owner_id": "uuid",
    "members": [
      {
        "user_id": "uuid",
        "role": "owner|admin|member|viewer",
        "joined_at": "datetime"
      }
    ],
    "settings": {
      "skill_sharing": bool,
      "task_collaboration": bool,
      "default_permissions": "list"
    },
    "created_at": "datetime",
    "plan": "free|pro|enterprise"
  }
  ```

---

### 2. 技能共享系统 (`core/collaboration/skill_sharing.py`)

#### 2.1 技能可见性
- **私人技能**：仅创建者可见
- **团队技能**：团队成员可见
- **公开技能**：所有用户可见（技能市场）

#### 2.2 技能版本控制
```python
{
  "skill_id": "uuid",
  "name": "string",
  "versions": [
    {
      "version": "1.0.0",
      "author_id": "uuid",
      "changes": "string",
      "created_at": "datetime",
      "is_published": bool
    }
  ],
  "current_version": "1.0.0",
  "visibility": "private|team|public",
  "team_id": "uuid|null",
  "collaborators": ["user_id"],
  "tags": ["list"]
}
```

#### 2.3 技能贡献统计
- 每个团队成员的贡献记录
- 下载量、使用次数、评价
- 收益分成

---

### 3. 任务协作系统 (`core/collaboration/task_manager.py`)

#### 3.1 任务类型
- **个人任务**：单人完成
- **团队任务**：多人协作
- **自动化流程**：多步骤工作流

#### 3.2 任务状态机
```
Draft → Assigned → In Progress → Review → Completed
         ↓                                    ↓
      On Hold                           Cancelled
```

#### 3.3 任务结构
```python
{
  "task_id": "uuid",
  "name": "string",
  "description": "string",
  "type": "personal|team|workflow",
  "owner_id": "uuid",
  "assignee_id": "uuid|null",
  "team_id": "uuid|null",
  "status": "draft|assigned|in_progress|review|completed|on_hold|cancelled",
  "priority": "low|medium|high|critical",
  "workflow": [
    {
      "step_id": "uuid",
      "name": "string",
      "skill_id": "uuid",
      "parameters": {},
      "order": int
    }
  ],
  "comments": [
    {
      "comment_id": "uuid",
      "user_id": "uuid",
      "content": "string",
      "created_at": "datetime"
    }
  ],
  "created_at": "datetime",
  "updated_at": "datetime",
  "due_date": "datetime|null"
}
```

#### 3.4 任务分配
- 手动分配
- 智能推荐（基于技能和负载）
- 抢单模式

---

### 4. 权限管理系统 (`core/collaboration/permission_manager.py`)

#### 4.1 角色定义

| 角色 | 技能管理 | 任务管理 | 团队管理 | 系统设置 |
|------|---------|---------|---------|---------|
| **Owner** | ✅ 完全控制 | ✅ 完全控制 | ✅ 完全控制 | ✅ 完全控制 |
| **Admin** | ✅ 创建/编辑 | ✅ 分配/审核 | ✅ 管理成员 | ✅ 部分设置 |
| **Member** | ⚠️ 创建/编辑自己的 | ⚠️ 查看所有 | ❌ | ❌ |
| **Viewer** | 🔒 仅查看 | 🔒 仅查看 | ❌ | ❌ |

#### 4.2 权限粒度
```python
PERMISSIONS = {
    "skill": {
        "create": bool,
        "read": bool,
        "update": bool,
        "delete": bool,
        "publish": bool,
        "share": bool
    },
    "task": {
        "create": bool,
        "read": bool,
        "update": bool,
        "delete": bool,
        "assign": bool,
        "complete": bool
    },
    "team": {
        "invite": bool,
        "remove": bool,
        "manage_roles": bool,
        "view_analytics": bool
    },
    "system": {
        "view_logs": bool,
        "export_data": bool,
        "manage_api_keys": bool
    }
}
```

#### 4.3 权限检查
```python
def check_permission(user_id, resource_type, action, resource_id=None):
    """
    检查用户是否有权限执行操作
    """
    # 1. 获取用户角色
    # 2. 检查角色权限
    # 3. 检查资源所有权
    # 4. 检查团队共享规则
    pass
```

---

### 5. 实时协作编辑 (`core/collaboration/realtime_collab.py`)

#### 5.1 WebSocket 服务
- 实时状态同步
- 操作转换（Operational Transformation）
- 冲突解决

#### 5.2 协作会话
```python
{
  "session_id": "uuid",
  "resource_type": "skill|workflow|config",
  "resource_id": "uuid",
  "participants": [
    {
      "user_id": "uuid",
      "username": "string",
      "cursor": {"line": int, "column": int},
      "status": "editing|idle|away"
    }
  ],
  "created_at": "datetime",
  "last_activity": "datetime"
}
```

#### 5.3 变更传播
- 操作序列化
- 增量同步
- 最终一致性

---

### 6. 活动日志 (`core/collaboration/activity_log.py`)

#### 6.1 事件类型
- 用户操作（登录、登出）
- 技能操作（创建、编辑、删除、发布）
- 任务操作（创建、分配、完成）
- 团队操作（邀请、移除、角色变更）
- 权限操作（授权、撤销）

#### 6.2 日志结构
```python
{
  "event_id": "uuid",
  "user_id": "uuid",
  "user_name": "string",
  "action": "string",
  "resource_type": "string",
  "resource_id": "uuid",
  "resource_name": "string",
  "details": {},
  "ip_address": "string",
  "timestamp": "datetime"
}
```

#### 6.3 审计导出
- CSV 导出
- PDF 报告
- 按时间/用户/操作类型过滤

---

## 数据库设计

### 7.1 表结构

```sql
-- 用户表
CREATE TABLE users (
    user_id UUID PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'member',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP,
    preferences JSONB
);

-- 团队表
CREATE TABLE teams (
    team_id UUID PRIMARY KEY,
    team_name VARCHAR(100) NOT NULL,
    description TEXT,
    owner_id UUID REFERENCES users(user_id),
    plan VARCHAR(20) DEFAULT 'free',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settings JSONB
);

-- 团队成员表
CREATE TABLE team_members (
    team_id UUID REFERENCES teams(team_id),
    user_id UUID REFERENCES users(user_id),
    role VARCHAR(20) DEFAULT 'member',
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (team_id, user_id)
);

-- 技能表（扩展现有）
ALTER TABLE skills ADD COLUMN visibility VARCHAR(20) DEFAULT 'private';
ALTER TABLE skills ADD COLUMN team_id UUID REFERENCES teams(team_id);
ALTER TABLE skills ADD COLUMN collaborators JSONB;

-- 任务表
CREATE TABLE tasks (
    task_id UUID PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    type VARCHAR(20) DEFAULT 'personal',
    owner_id UUID REFERENCES users(user_id),
    assignee_id UUID REFERENCES users(user_id),
    team_id UUID REFERENCES teams(team_id),
    status VARCHAR(20) DEFAULT 'draft',
    priority VARCHAR(20) DEFAULT 'medium',
    workflow JSONB,
    comments JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    due_date TIMESTAMP
);

-- 活动日志表
CREATE TABLE activity_logs (
    event_id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(user_id),
    user_name VARCHAR(50),
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id UUID,
    resource_name VARCHAR(200),
    details JSONB,
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## API 设计

### 8.1 团队管理 API

```python
# 创建团队
POST /api/teams
{
  "team_name": "string",
  "description": "string",
  "plan": "free|pro|enterprise"
}

# 获取团队列表
GET /api/teams?user_id={user_id}

# 更新团队信息
PUT /api/teams/{team_id}

# 删除团队
DELETE /api/teams/{team_id}
```

### 8.2 成员管理 API

```python
# 邀请成员
POST /api/teams/{team_id}/members
{
  "email": "string",
  "role": "admin|member|viewer"
}

# 移除成员
DELETE /api/teams/{team_id}/members/{user_id}

# 更新成员角色
PUT /api/teams/{team_id}/members/{user_id}/role
{
  "role": "admin|member|viewer"
}
```

### 8.3 技能共享 API

```python
# 共享技能到团队
POST /api/skills/{skill_id}/share
{
  "team_id": "uuid",
  "visibility": "team"
}

# 获取团队技能
GET /api/teams/{team_id}/skills

# 添加技能协作者
POST /api/skills/{skill_id}/collaborators
{
  "user_id": "uuid",
  "permissions": ["read", "update"]
}
```

### 8.4 任务协作 API

```python
# 创建团队任务
POST /api/tasks
{
  "name": "string",
  "description": "string",
  "type": "team",
  "team_id": "uuid",
  "assignee_id": "uuid",
  "priority": "high"
}

# 分配任务
POST /api/tasks/{task_id}/assign
{
  "assignee_id": "uuid"
}

# 添加评论
POST /api/tasks/{task_id}/comments
{
  "content": "string"
}

# 更新任务状态
PUT /api/tasks/{task_id}/status
{
  "status": "completed"
}
```

### 8.5 实时协作 WebSocket

```python
# 连接
WS /api/realtime?session_id={session_id}&user_id={user_id}

# 消息格式
{
  "type": "operation|cursor|presence",
  "resource_type": "skill|workflow",
  "resource_id": "uuid",
  "data": {}
}
```

---

## 安全设计

### 9.1 认证与授权
- **认证**：JWT Token + Refresh Token
- **授权**：基于角色的访问控制（RBAC）
- **API 限流**：防止滥用

### 9.2 数据加密
- 传输加密：HTTPS/TLS
- 存储加密：敏感字段 AES-256 加密
- 密码：bcrypt 哈希

### 9.3 审计日志
- 所有关键操作记录
- 不可篡改（区块链存证可选）
- 定期审查

---

## 实施计划

### Phase 1: 基础架构（2 周）
- ✅ 用户与团队管理系统
- ✅ 权限管理系统
- ✅ 数据库迁移脚本

### Phase 2: 技能共享（1 周）
- ⬜ 技能可见性控制
- ⬜ 团队技能库
- ⬜ 技能版本管理

### Phase 3: 任务协作（2 周）
- ⬜ 任务管理系统
- ⬜ 任务分配与跟踪
- ⬜ 工作流编辑器

### Phase 4: 实时协作（2 周）
- ⬜ WebSocket 服务
- ⬜ 操作转换引擎
- ⬜ 在线状态同步

### Phase 5: 测试与优化（1 周）
- ⬜ 单元测试
- ⬜ 集成测试
- ⬜ 性能优化

---

## 技术栈

### 后端
- **框架**：FastAPI（异步、高性能）
- **数据库**：SQLite（开发） / PostgreSQL（生产）
- **缓存**：Redis（会话、实时数据）
- **WebSocket**：FastAPI WebSocket
- **认证**：PyJWT

### 前端
- **框架**：Vue.js 3 + Vite
- **UI 库**：Element Plus
- **状态管理**：Pinia
- **实时通信**：Socket.IO

### 工具
- **测试**：pytest
- **代码质量**：black, flake8, mypy
- **文档**：Sphinx

---

## 成功指标

### 用户指标
- 注册团队数：100+（3 个月）
- 平均团队规模：5-10 人
- 技能共享率：>60%
- 任务协作率：>40%

### 技术指标
- API 响应时间：<200ms (P95)
- WebSocket 延迟：<50ms
- 并发用户数：1000+
- 系统可用性：>99.9%

### 业务指标
- 企业版转化率：>20%
- 客户留存率：>80%
- NPS（净推荐值）：>50

---

## 总结

NovaHands 协作系统将提供企业级的团队协作能力，通过清晰的权限体系、实时的协作编辑和智能的任务分配，帮助团队提高工作效率。

核心优势：
- ✅ 灵活的权限管理
- ✅ 实时协作编辑
- ✅ 智能任务分配
- ✅ 完整的审计日志
- ✅ 可扩展的架构设计
