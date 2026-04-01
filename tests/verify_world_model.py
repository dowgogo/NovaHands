"""
世界模型验证脚本

简化版测试，验证核心功能。
"""

import sys
from pathlib import Path

# 设置输出编码为 UTF-8
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from world_model.data import WorldModelTransition, WorldModelDataset
from world_model.encoder import SimpleObservationEncoder, EncoderConfig
from world_model.dynamics import DynamicsModel, DynamicsConfig
from world_model.reward import RewardModel, RewardConfig
from world_model.world_model import WorldModel, WorldModelConfig
from world_model.planner import LatentPlanner, PlannerConfig


def test_data_structures():
    """测试数据结构"""
    print("\n=== 测试数据结构 ===")
    
    # 创建 Transition
    transition = WorldModelTransition(
        observation={"test": "data"},
        action="click",
        reward=1.0,
        next_observation={"test": "next"},
        done=False,
        timestamp=123.0
    )
    print(f"[OK] 创建 Transition: action={transition.action}, reward={transition.reward}")
    
    # 创建 Dataset
    dataset = WorldModelDataset()
    dataset.add(
        observation={"test": "data"},
        action="click",
        reward=1.0
    )
    dataset.add(
        observation={"test": "data2"},
        action="type",
        reward=0.5
    )
    print(f"[OK] 创建 Dataset: size={len(dataset)}, skills={list(dataset.skill_vocab.keys())}")
    
    # 获取统计
    stats = dataset.get_statistics()
    print(f"[OK] 数据集统计: {stats}")
    
    return True


def test_encoder():
    """测试编码器"""
    print("\n=== 测试编码器 ===")
    
    # 创建编码器
    config = EncoderConfig(latent_dim=64)
    encoder = SimpleObservationEncoder(config)
    print(f"[OK] 创建编码器: latent_dim={config.latent_dim}")
    
    # 编码观察
    observation = {
        "window_title": "Notepad",
        "active_app": "notepad.exe",
        "cursor_pos": (100, 200)
    }
    latent = encoder.encode(observation)
    print(f"[OK] 编码观察: latent_shape={latent.shape}")
    
    # 批量编码
    observations = [
        {"window_title": "App1", "active_app": "app1.exe", "cursor_pos": (0, 0)},
        {"window_title": "App2", "active_app": "app2.exe", "cursor_pos": (100, 100)},
    ]
    latents = encoder.encode_batch(observations)
    print(f"[OK] 批量编码: batch_shape={latents.shape}")
    
    return True


def test_dynamics_model():
    """测试动态模型"""
    print("\n=== 测试动态模型 ===")
    
    # 创建模型
    config = DynamicsConfig(
        input_dim=192,
        output_dim=128,
        num_ensembles=3
    )
    model = DynamicsModel(config)
    print(f"[OK] 创建动态模型: num_ensembles={config.num_ensembles}")
    
    # 预测
    state = np.random.randn(128)
    action = np.random.randn(64)
    next_state, uncertainty = model.predict(state, action)
    print(f"[OK] 预测: next_state_shape={next_state.shape}, uncertainty={uncertainty:.4f}")
    
    # 批量预测
    states = np.random.randn(5, 128)
    actions = np.random.randn(5, 64)
    next_states, uncertainties = model.predict_batch(states, actions)
    print(f"[OK] 批量预测: batch_shape={next_states.shape}")
    
    # 训练（少量数据）
    dataset = []
    for _ in range(50):
        state = np.random.randn(128)
        action = np.random.randn(64)
        next_state = state + np.random.randn(128) * 0.1
        dataset.append((state, action, next_state))
    
    model.train(dataset, epochs=3)
    print("[OK] 训练动态模型（3 epochs）")
    
    return True


def test_reward_model():
    """测试奖励模型"""
    print("\n=== 测试奖励模型 ===")
    
    # 创建模型
    config = RewardConfig(input_dim=128, hidden_dim=64)
    model = RewardModel(config)
    print(f"[OK] 创建奖励模型: input_dim={config.input_dim}")
    
    # 预测
    state = np.random.randn(128)
    reward = model.predict(state)
    print(f"[OK] 预测奖励: reward={reward:.4f}")
    
    # 批量预测
    states = np.random.randn(10, 128)
    rewards = model.predict_batch(states)
    print(f"[OK] 批量预测: batch_shape={rewards.shape}")
    
    # 训练
    dataset = []
    for _ in range(50):
        state = np.random.randn(128)
        reward = np.random.randn()
        dataset.append((state, reward))
    
    model.train(dataset, epochs=3)
    print("[OK] 训练奖励模型（3 epochs）")
    
    return True


def test_world_model():
    """测试世界模型"""
    print("\n=== 测试世界模型 ===")
    
    # 创建世界模型
    config = WorldModelConfig(
        encoder_config=EncoderConfig(latent_dim=64),
        action_embedding_dim=32
    )
    model = WorldModel(config)
    print(f"[OK] 创建世界模型: latent_dim=64, action_dim=32")
    
    # 编码观察
    observation = {
        "window_title": "Notepad",
        "active_app": "notepad.exe",
        "cursor_pos": (100, 200)
    }
    state = model.encode_observation(observation)
    print(f"[OK] 编码观察: state_shape={state.shape}")
    
    # 预测下一状态
    action = "click"
    next_state, uncertainty = model.predict_next_state(state, action)
    print(f"[OK] 预测下一状态: next_state_shape={next_state.shape}, uncertainty={uncertainty:.4f}")
    
    # 预测奖励
    reward = model.predict_reward(state)
    print(f"[OK] 预测奖励: reward={reward:.4f}")
    
    # 想象回放
    action_sequence = ["click", "type", "scroll"]
    states, rewards, uncertainties = model.imagine_rollout(
        state,
        action_sequence
    )
    print(f"[OK] 想象回放: states={len(states)}, rewards={len(rewards)}, total_reward={sum(rewards[1:]):.4f}")
    
    # 收集训练数据
    observations = [
        {"window_title": f"App{i}", "active_app": f"app{i}.exe", "cursor_pos": (i * 10, i * 10)}
        for i in range(10)
    ]
    actions = ["click", "type", "scroll"] * 3 + ["click"]
    rewards = [np.random.randn() for _ in range(10)]
    
    dataset = model.collect_training_data(
        observations,
        actions,
        rewards
    )
    print(f"[OK] 收集训练数据: dataset_size={len(dataset)}")
    
    # 训练
    model.train(dataset, epochs_dynamics=3, epochs_reward=3)
    print("[OK] 训练世界模型（3 epochs）")
    
    # 评估
    metrics = model.evaluate(dataset, num_samples=10)
    print(f"[OK] 评估模型: dynamics_mse={metrics['dynamics_mse']:.6f}, reward_mse={metrics['reward_mse']:.6f}")
    
    return True


def test_planner():
    """测试规划器"""
    print("\n=== 测试规划器 ===")
    
    # 创建世界模型
    config = WorldModelConfig(
        encoder_config=EncoderConfig(latent_dim=64),
        action_embedding_dim=32
    )
    world_model = WorldModel(config)
    
    # 简单训练（使模型可用）
    observations = [
        {"window_title": f"App{i}", "active_app": f"app{i}.exe", "cursor_pos": (i * 10, i * 10)}
        for i in range(10)
    ]
    actions = ["click", "type", "scroll"] * 3 + ["click"]
    dataset = world_model.collect_training_data(observations, actions)
    world_model.train(dataset, epochs_dynamics=2, epochs_reward=2)
    
    # 创建规划器
    planner_config = PlannerConfig(
        horizon=5,
        num_candidates=20,
        planning_method="random_shooting"
    )
    planner = LatentPlanner(world_model, planner_config)
    print(f"[OK] 创建规划器: method={planner_config.planning_method}, horizon={planner_config.horizon}")
    
    # 规划
    state = np.random.randn(64)
    available_actions = ["click", "type", "scroll"]
    
    best_action, expected_return, action_sequence = planner.plan(
        state,
        available_actions,
        horizon=3
    )
    print(f"[OK] 规划: best_action={best_action}, expected_return={expected_return:.4f}, sequence={action_sequence}")
    
    # 可视化
    vis = planner.visualize_plan(state, action_sequence)
    print(f"[OK] 可视化: total_reward={vis['total_reward']:.4f}, avg_uncertainty={vis['avg_uncertainty']:.4f}")
    
    return True


def main():
    """主函数"""
    print("=" * 70)
    print("世界模型验证测试")
    print("=" * 70)
    
    tests = [
        ("数据结构", test_data_structures),
        ("编码器", test_encoder),
        ("动态模型", test_dynamics_model),
        ("奖励模型", test_reward_model),
        ("世界模型", test_world_model),
        ("规划器", test_planner),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {name} 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    # 打印摘要
    print("\n" + "=" * 70)
    print("测试摘要")
    print("=" * 70)
    print(f"总计: {len(tests)}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    
    if failed == 0:
        print("\n[SUCCESS] 所有测试通过！")
        return 0
    else:
        print(f"\n[FAIL] {failed} 个测试失败")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
