"""
协作系统测试

测试用户管理、团队管理、权限管理、技能共享、任务协作、活动日志等功能。
"""

import os
import sys
import tempfile
import shutil
from datetime import datetime, timedelta

# 设置 UTF-8 编码输出
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from core.collaboration.user_manager import (
    UserManager,
    TeamManager,
    User,
    Team,
    UserRole,
    TeamPlan
)
from core.collaboration.permission_manager import (
    PermissionManager,
    Permission,
    ResourceType
)
from core.collaboration.skill_sharing import (
    SkillSharingManager,
    SharedSkill,
    SkillVisibility
)
from core.collaboration.task_manager import (
    TaskManager,
    Task,
    TaskStatus,
    TaskPriority,
    TaskType
)
from core.collaboration.activity_log import (
    ActivityLogger,
    ActionType,
    ResourceType as ActivityResourceType
)


def print_section(title: str):
    """打印测试章节"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def test_user_management():
    """测试用户管理"""
    print_section("1. 用户管理测试")
    
    user_manager = UserManager()
    
    # 1.1 注册用户
    print("  1.1 注册用户...")
    alice = user_manager.register("alice", "alice@example.com", "hashed_password")
    bob = user_manager.register("bob", "bob@example.com", "hashed_password")
    charlie = user_manager.register("charlie", "charlie@example.com", "hashed_password")
    print(f"      ✅ 已注册 3 个用户: {alice.username}, {bob.username}, {charlie.username}")
    
    # 1.2 获取用户
    print("  1.2 获取用户...")
    retrieved_user = user_manager.get_user(alice.user_id)
    assert retrieved_user.user_id == alice.user_id
    print(f"      ✅ 成功获取用户: {retrieved_user.username}")
    
    # 1.3 通过邮箱获取用户
    print("  1.3 通过邮箱获取用户...")
    email_user = user_manager.get_user_by_email("bob@example.com")
    assert email_user.username == "bob"
    print(f"      ✅ 成功通过邮箱获取用户: {email_user.username}")
    
    # 1.4 更新用户
    print("  1.4 更新用户...")
    user_manager.update_user(charlie.user_id, role=UserRole.ADMIN)
    updated_charlie = user_manager.get_user(charlie.user_id)
    assert updated_charlie.role == UserRole.ADMIN
    print(f"      ✅ 成功更新用户角色: {updated_charlie.username} -> {updated_charlie.role.value}")
    
    # 1.5 重复注册测试
    print("  1.5 重复注册测试...")
    try:
        user_manager.register("alice", "alice@example.com", "password")
        print("      ❌ 应该抛出异常")
        return False
    except ValueError as e:
        print(f"      ✅ 正确抛出异常: {e}")
    
    return True, user_manager, alice, bob, charlie


def test_team_management(user_manager, alice, bob, charlie):
    """测试团队管理"""
    print_section("2. 团队管理测试")
    
    team_manager = TeamManager(user_manager)
    
    # 2.1 创建团队
    print("  2.1 创建团队...")
    team = team_manager.create_team(
        owner_id=alice.user_id,
        team_name="NovaHands 团队",
        description="智能桌面助手团队",
        plan=TeamPlan.PRO
    )
    print(f"      ✅ 成功创建团队: {team.team_name} (ID: {team.team_id})")
    print(f"      计划: {team.plan.value}, 成员数: {len(team.members)}")
    
    # 2.2 邀请成员
    print("  2.2 邀请成员...")
    team_manager.invite_member(team.team_id, alice.user_id, bob.user_id, UserRole.MEMBER)
    team_manager.invite_member(team.team_id, alice.user_id, charlie.user_id, UserRole.ADMIN)
    print(f"      ✅ 成功邀请成员: Bob (Member), Charlie (Admin)")
    
    # 2.3 获取用户团队
    print("  2.3 获取用户团队...")
    alice_teams = team_manager.get_user_teams(alice.user_id)
    bob_teams = team_manager.get_user_teams(bob.user_id)
    print(f"      ✅ Alice 团队数: {len(alice_teams)}, Bob 团队数: {len(bob_teams)}")
    
    # 2.4 获取团队成员
    print("  2.4 获取团队成员...")
    updated_team = team_manager.get_team(team.team_id)
    print(f"      ✅ 团队成员数: {len(updated_team.members)}")
    for member in updated_team.members:
        print(f"         - {member.username} ({member.role.value})")
    
    # 2.5 更新成员角色
    print("  2.5 更新成员角色...")
    team_manager.update_member_role(team.team_id, alice.user_id, bob.user_id, UserRole.ADMIN)
    print(f"      ✅ 成功将 Bob 升级为 Admin")
    
    # 2.6 移除成员测试
    print("  2.6 移除成员测试...")
    try:
        team_manager.remove_member(team.team_id, alice.user_id, alice.user_id)
        print("      ❌ 不应该能移除所有者")
        return False
    except ValueError as e:
        print(f"      ✅ 正确抛出异常: {e}")
    
    return True, team_manager, team


def test_permission_management():
    """测试权限管理"""
    print_section("3. 权限管理测试")
    
    permission_manager = PermissionManager()
    
    # 3.1 检查角色权限
    print("  3.1 检查角色权限...")
    
    # Owner 权限
    owner_can_create = permission_manager.has_permission(
        "user1", UserRole.OWNER, Permission.SKILL_CREATE
    )
    assert owner_can_create == True
    print(f"      ✅ Owner 可以创建技能: {owner_can_create}")
    
    # Viewer 权限
    viewer_can_delete = permission_manager.has_permission(
        "user2", UserRole.VIEWER, Permission.SKILL_DELETE
    )
    assert viewer_can_delete == False
    print(f"      ✅ Viewer 不能删除技能: {not viewer_can_delete}")
    
    # 3.2 检查资源权限
    print("  3.2 检查资源权限...")
    
    # Member 编辑自己的技能
    can_edit_own = permission_manager.check_resource_permission(
        user_id="user1",
        role=UserRole.MEMBER,
        resource_type=ResourceType.SKILL,
        action="update",
        resource_owner_id="user1"
    )
    assert can_edit_own == True
    print(f"      ✅ Member 可以编辑自己的技能: {can_edit_own}")
    
    # Member 编辑他人的技能
    cannot_edit_other = permission_manager.check_resource_permission(
        user_id="user1",
        role=UserRole.MEMBER,
        resource_type=ResourceType.SKILL,
        action="update",
        resource_owner_id="user2"
    )
    assert cannot_edit_other == False
    print(f"      ✅ Member 不能编辑他人的技能: {not cannot_edit_other}")
    
    # 3.3 获取权限矩阵
    print("  3.3 获取权限矩阵...")
    matrix = permission_manager.get_permission_matrix(UserRole.ADMIN)
    print(f"      ✅ Admin 权限数: {len(matrix['admin'])}")
    print(f"         前 5 个权限: {matrix['admin'][:5]}")
    
    # 3.4 自定义权限
    print("  3.4 自定义权限...")
    permission_manager.grant_custom_permission(
        user_id="user1",
        team_id="team1",
        permission=Permission.SKILL_PUBLISH
    )
    user_perms = permission_manager.get_user_permissions(
        user_id="user1",
        role=UserRole.MEMBER,
        team_id="team1"
    )
    print(f"      ✅ 自定义权限已添加: {Permission.SKILL_PUBLISH.value in user_perms}")
    
    return True, permission_manager


def test_skill_sharing(user_manager, team_manager, team, alice, bob):
    """测试技能共享"""
    print_section("4. 技能共享测试")
    
    skill_manager = SkillSharingManager(user_manager, team_manager)
    
    # 4.1 创建私人技能
    print("  4.1 创建私人技能...")
    skill1 = skill_manager.create_skill(
        owner_id=alice.user_id,
        owner_name=alice.username,
        name="Excel 报表生成",
        visibility=SkillVisibility.PRIVATE,
        description="自动生成 Excel 报表",
        tags=["excel", "automation"]
    )
    print(f"      ✅ 创建私人技能: {skill1.name} (ID: {skill1.skill_id})")
    
    # 4.2 创建团队技能
    print("  4.2 创建团队技能...")
    skill2 = skill_manager.create_skill(
        owner_id=alice.user_id,
        owner_name=alice.username,
        name="邮件批量发送",
        visibility=SkillVisibility.TEAM,
        team_id=team.team_id,
        description="批量发送邮件",
        tags=["email", "batch"]
    )
    print(f"      ✅ 创建团队技能: {skill2.name} (ID: {skill2.skill_id})")
    
    # 4.3 创建公开技能
    print("  4.3 创建公开技能...")
    skill3 = skill_manager.create_skill(
        owner_id=bob.user_id,
        owner_name=bob.username,
        name="PDF 文件转换",
        visibility=SkillVisibility.PUBLIC,
        description="转换 PDF 文件格式",
        tags=["pdf", "conversion"]
    )
    print(f"      ✅ 创建公开技能: {skill3.name} (ID: {skill3.skill_id})")
    
    # 4.4 添加技能版本
    print("  4.4 添加技能版本...")
    version1 = skill_manager.add_skill_version(
        skill_id=skill1.skill_id,
        user_id=alice.user_id,
        user_name=alice.username,
        version="1.1.0",
        changes="优化报表格式"
    )
    print(f"      ✅ 添加版本: {version1.version}")
    
    # 4.5 添加协作者
    print("  4.5 添加协作者...")
    skill_manager.add_collaborator(
        skill_id=skill1.skill_id,
        owner_id=alice.user_id,
        collaborator_id=bob.user_id
    )
    print(f"      ✅ 添加协作者: Bob")
    
    # 4.6 搜索技能
    print("  4.6 搜索技能...")
    results = skill_manager.search_skills(
        user_id=alice.user_id,
        keyword="邮件"
    )
    print(f"      ✅ 搜索结果: {len(results)} 个技能")
    for skill in results:
        print(f"         - {skill.name} ({skill.visibility.value})")
    
    # 4.7 获取团队技能
    print("  4.7 获取团队技能...")
    team_skills = skill_manager.get_team_skills(team.team_id, alice.user_id)
    print(f"      ✅ 团队技能数: {len(team_skills)}")
    
    # 4.8 更新可见性
    print("  4.8 更新可见性...")
    skill_manager.update_skill_visibility(
        skill_id=skill1.skill_id,
        user_id=alice.user_id,
        visibility=SkillVisibility.TEAM,
        team_id=team.team_id
    )
    print(f"      ✅ 技能可见性已更新: PRIVATE -> TEAM")
    
    return True, skill_manager, skill1, skill2, skill3


def test_task_management(user_manager, team_manager, team, alice, bob):
    """测试任务管理"""
    print_section("5. 任务管理测试")
    
    task_manager = TaskManager(user_manager, team_manager)
    
    # 5.1 创建个人任务
    print("  5.1 创建个人任务...")
    task1 = task_manager.create_task(
        name="整理桌面文件",
        owner_id=alice.user_id,
        owner_name=alice.username,
        description="整理桌面上的所有文件",
        task_type=TaskType.PERSONAL,
        priority=TaskPriority.MEDIUM
    )
    print(f"      ✅ 创建个人任务: {task1.name} (ID: {task1.task_id})")
    
    # 5.2 创建团队任务
    print("  5.2 创建团队任务...")
    task2 = task_manager.create_task(
        name="优化技能库",
        owner_id=alice.user_id,
        owner_name=alice.username,
        description="优化团队技能库的性能",
        task_type=TaskType.TEAM,
        team_id=team.team_id,
        priority=TaskPriority.HIGH
    )
    print(f"      ✅ 创建团队任务: {task2.name} (ID: {task2.task_id})")
    
    # 5.3 分配任务
    print("  5.3 分配任务...")
    task_manager.assign_task(
        task_id=task2.task_id,
        assignee_id=bob.user_id,
        assignee_name=bob.username,
        operator_id=alice.user_id
    )
    print(f"      ✅ 任务已分配: {task2.name} -> {bob.username}")
    
    # 5.4 添加工作流步骤
    print("  5.4 添加工作流步骤...")
    step1 = task2.add_workflow_step(
        name="备份技能库",
        skill_id="skill_backup",
        parameters={"path": "/skills"}
    )
    step2 = task2.add_workflow_step(
        name="优化代码",
        skill_id="skill_optimize",
        parameters={"level": "deep"}
    )
    print(f"      ✅ 添加 {len(task2.workflow)} 个工作流步骤")
    
    # 5.5 更新任务状态
    print("  5.5 更新任务状态...")
    task_manager.update_task_status(
        task_id=task2.task_id,
        status=TaskStatus.IN_PROGRESS,
        user_id=bob.user_id
    )
    print(f"      ✅ 任务状态已更新: {task2.status.value}")
    
    # 5.6 添加评论
    print("  5.6 添加评论...")
    comment = task_manager.add_task_comment(
        task_id=task2.task_id,
        user_id=bob.user_id,
        user_name=bob.username,
        content="正在优化中，预计 2 小时完成"
    )
    print(f"      ✅ 添加评论: {comment.content}")
    
    # 5.7 完成任务
    print("  5.7 完成任务...")
    task_manager.update_task_status(
        task_id=task2.task_id,
        status=TaskStatus.COMPLETED,
        user_id=bob.user_id
    )
    print(f"      ✅ 任务已完成: {task2.name}")
    
    # 5.8 搜索任务
    print("  5.8 搜索任务...")
    results = task_manager.search_tasks(
        user_id=alice.user_id,
        keyword="优化"
    )
    print(f"      ✅ 搜索结果: {len(results)} 个任务")
    
    return True, task_manager, task1, task2


def test_activity_log(user_manager, alice, bob, skill_manager, skill1, task_manager, task2):
    """测试活动日志"""
    print_section("6. 活动日志测试")
    
    logger = ActivityLogger()
    
    # 6.1 记录用户操作
    print("  6.1 记录用户操作...")
    logger.log(
        user_id=alice.user_id,
        user_name=alice.username,
        action=ActionType.USER_LOGIN,
        resource_type=ActivityResourceType.USER,
        ip_address="192.168.1.1"
    )
    logger.log(
        user_id=bob.user_id,
        user_name=bob.username,
        action=ActionType.USER_LOGIN,
        resource_type=ActivityResourceType.USER,
        ip_address="192.168.1.2"
    )
    print(f"      ✅ 记录了 2 条用户登录日志")
    
    # 6.2 记录技能操作
    print("  6.2 记录技能操作...")
    logger.log(
        user_id=alice.user_id,
        user_name=alice.username,
        action=ActionType.SKILL_CREATE,
        resource_type=ActivityResourceType.SKILL,
        resource_id=skill1.skill_id,
        resource_name=skill1.name
    )
    print(f"      ✅ 记录了技能创建日志")
    
    # 6.3 记录任务操作
    print("  6.3 记录任务操作...")
    logger.log(
        user_id=alice.user_id,
        user_name=alice.username,
        action=ActionType.TASK_ASSIGN,
        resource_type=ActivityResourceType.TASK,
        resource_id=task2.task_id,
        resource_name=task2.name,
        details={"assignee": bob.username}
    )
    print(f"      ✅ 记录了任务分配日志")
    
    # 6.4 获取用户日志
    print("  6.4 获取用户日志...")
    alice_logs = logger.get_logs(user_id=alice.user_id)
    print(f"      ✅ Alice 的日志数: {len(alice_logs)}")
    
    # 6.5 用户活动摘要
    print("  6.5 用户活动摘要...")
    alice_summary = logger.get_user_activity_summary(alice.user_id)
    print(f"      ✅ Alice 活动摘要:")
    print(f"         总操作数: {alice_summary['total_actions']}")
    print(f"         操作类型: {list(alice_summary['action_counts'].keys())}")
    
    # 6.6 团队活动摘要
    print("  6.6 团队活动摘要...")
    team_summary = logger.get_team_activity_summary(
        team_id="team1",
        team_members={alice.user_id, bob.user_id}
    )
    print(f"      ✅ 团队活动摘要:")
    print(f"         总操作数: {team_summary['total_actions']}")
    print(f"         活跃成员: {team_summary['active_members']}")
    
    # 6.7 获取统计信息
    print("  6.7 获取统计信息...")
    stats = logger.get_statistics()
    print(f"      ✅ 日志统计:")
    print(f"         总日志数: {stats['total_logs']}")
    print(f"         唯一用户: {stats['unique_users']}")
    print(f"         操作类型: {list(stats['action_types'].keys())}")
    
    # 6.8 导出 CSV
    print("  6.8 导出 CSV...")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        csv_file = f.name
    logger.export_to_csv(csv_file, user_id=alice.user_id)
    print(f"      ✅ CSV 已导出到: {csv_file}")
    
    return True, logger


def test_integration():
    """集成测试"""
    print_section("7. 集成测试")
    
    # 7.1 初始化所有管理器
    print("  7.1 初始化系统...")
    user_manager = UserManager()
    team_manager = TeamManager(user_manager)
    permission_manager = PermissionManager()
    skill_manager = SkillSharingManager(user_manager, team_manager)
    task_manager = TaskManager(user_manager, team_manager)
    logger = ActivityLogger()
    print("      ✅ 系统初始化完成")
    
    # 7.2 注册用户
    print("  7.2 注册用户...")
    alice = user_manager.register("alice", "alice@company.com", "hashed")
    bob = user_manager.register("bob", "bob@company.com", "hashed")
    charlie = user_manager.register("charlie", "charlie@company.com", "hashed")
    print(f"      ✅ 已注册 {len(user_manager.users)} 个用户")
    
    # 7.3 创建团队
    print("  7.3 创建团队...")
    team = team_manager.create_team(
        owner_id=alice.user_id,
        team_name="技术团队",
        plan=TeamPlan.PRO
    )
    team_manager.invite_member(team.team_id, alice.user_id, bob.user_id, UserRole.ADMIN)
    team_manager.invite_member(team.team_id, alice.user_id, charlie.user_id, UserRole.MEMBER)
    print(f"      ✅ 团队成员: {len(team.members)} 人")
    
    # 7.4 创建和共享技能
    print("  7.4 创建和共享技能...")
    skill = skill_manager.create_skill(
        owner_id=alice.user_id,
        owner_name=alice.username,
        name="自动化部署脚本",
        visibility=SkillVisibility.TEAM,
        team_id=team.team_id
    )
    skill_manager.add_collaborator(skill.skill_id, alice.user_id, bob.user_id)
    print(f"      ✅ 创建团队技能: {skill.name}")
    
    # 7.5 创建和分配任务
    print("  7.5 创建和分配任务...")
    task = task_manager.create_task(
        name="优化部署流程",
        owner_id=alice.user_id,
        owner_name=alice.username,
        task_type=TaskType.TEAM,
        team_id=team.team_id,
        priority=TaskPriority.HIGH
    )
    task_manager.assign_task(task.task_id, bob.user_id, bob.username, alice.user_id)
    print(f"      ✅ 创建团队任务: {task.name}")
    
    # 7.6 记录活动
    print("  7.6 记录活动...")
    logger.log(
        user_id=alice.user_id,
        user_name=alice.username,
        action=ActionType.TEAM_CREATE,
        resource_type=ActivityResourceType.TEAM,
        resource_id=team.team_id,
        resource_name=team.team_name
    )
    logger.log(
        user_id=alice.user_id,
        user_name=alice.username,
        action=ActionType.SKILL_SHARE,
        resource_type=ActivityResourceType.SKILL,
        resource_id=skill.skill_id,
        resource_name=skill.name
    )
    print(f"      ✅ 记录活动日志")
    
    # 7.7 权限验证
    print("  7.7 权限验证...")
    alice_role = team.get_member(alice.user_id).role
    can_create_skill = permission_manager.has_permission(
        alice.user_id,
        alice_role,
        Permission.SKILL_CREATE
    )
    print(f"      ✅ Alice ({alice_role.value}) 可以创建技能: {can_create_skill}")
    
    # 7.8 获取团队统计
    print("  7.8 获取团队统计...")
    team_skills = skill_manager.get_team_skills(team.team_id, alice.user_id)
    team_tasks = task_manager.get_team_tasks(team.team_id)
    team_summary = logger.get_team_activity_summary(
        team.team_id,
        {m.user_id for m in team.members}
    )
    print(f"      ✅ 团队统计:")
    print(f"         技能数: {len(team_skills)}")
    print(f"         任务数: {len(team_tasks)}")
    print(f"         活动数: {team_summary['total_actions']}")
    
    print(f"\n  ✅ 集成测试完成！")
    print(f"     用户: {len(user_manager.users)}")
    print(f"     团队: {len(team_manager.teams)}")
    print(f"     技能: {len(skill_manager.skills)}")
    print(f"     任务: {len(task_manager.tasks)}")
    print(f"     日志: {len(logger.logs)}")
    
    return True


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("  NovaHands 协作系统测试")
    print("=" * 60)
    
    results = []
    
    try:
        # 测试用户管理
        result = test_user_management()
        if isinstance(result, tuple) and result[0]:
            results.append(("用户管理", "✅ 通过"))
            _, user_manager, alice, bob, charlie = result
            
            # 测试团队管理
            result = test_team_management(user_manager, alice, bob, charlie)
            if isinstance(result, tuple) and result[0]:
                results.append(("团队管理", "✅ 通过"))
                _, team_manager, team = result
                
                # 测试权限管理
                result = test_permission_management()
                if isinstance(result, tuple) and result[0]:
                    results.append(("权限管理", "✅ 通过"))
                    _, permission_manager = result
                    
                    # 测试技能共享
                    result = test_skill_sharing(user_manager, team_manager, team, alice, bob)
                    if isinstance(result, tuple) and result[0]:
                        results.append(("技能共享", "✅ 通过"))
                        _, skill_manager, skill1, skill2, skill3 = result
                        
                        # 测试任务管理
                        result = test_task_management(user_manager, team_manager, team, alice, bob)
                        if isinstance(result, tuple) and result[0]:
                            results.append(("任务管理", "✅ 通过"))
                            _, task_manager, task1, task2 = result
                            
                            # 测试活动日志
                            result = test_activity_log(user_manager, alice, bob, skill_manager, skill1, task_manager, task2)
                            if isinstance(result, tuple) and result[0]:
                                results.append(("活动日志", "✅ 通过"))
                            else:
                                results.append(("活动日志", "❌ 失败"))
                        else:
                            results.append(("任务管理", "❌ 失败"))
                    else:
                        results.append(("技能共享", "❌ 失败"))
                else:
                    results.append(("权限管理", "❌ 失败"))
            else:
                results.append(("团队管理", "❌ 失败"))
        else:
            results.append(("用户管理", "❌ 失败"))
        
        # 集成测试
        print_section("运行集成测试")
        if test_integration():
            results.append(("集成测试", "✅ 通过"))
        else:
            results.append(("集成测试", "❌ 失败"))
    
    except Exception as e:
        print(f"\n❌ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("系统", "❌ 异常"))
    
    # 打印结果摘要
    print_section("测试结果摘要")
    passed = sum(1 for _, status in results if "通过" in status)
    total = len(results)
    
    for name, status in results:
        print(f"  {name:20s} {status}")
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！")
        return True
    else:
        print(f"\n⚠️  {total - passed} 个测试失败")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
