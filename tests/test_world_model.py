"""
世界模型测试套件

测试世界模型各组件的功能。
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import unittest
import numpy as np
from pathlib import Path as FilePath
import tempfile
import shutil

from world_model.data import WorldModelTransition, WorldModelDataset
from world_model.encoder import (
    ObservationEncoder,
    SimpleObservationEncoder,
    EncoderConfig,
    create_encoder
)
from world_model.dynamics import DynamicsModel, DynamicsConfig
from world_model.reward import RewardModel, RewardConfig
from world_model.planner import LatentPlanner, PlannerConfig
from world_model.world_model import WorldModel, WorldModelConfig
from world_model.trainer import WorldModelTrainer


class TestWorldModelData(unittest.TestCase):
    """测试数据结构"""
    
    def test_transition_creation(self):
        """测试创建 Transition"""
        transition = WorldModelTransition(
            observation={"test": "data"},
            action="click",
            reward=1.0,
            next_observation={"test": "next"},
            done=False,
            timestamp=123.0
        )
        self.assertEqual(transition.action, "click")
        self.assertEqual(transition.reward, 1.0)
    
    def test_transition_serialization(self):
        """测试 Transition 序列化"""
        transition = WorldModelTransition(
            observation={"test": "data"},
            action="click",
            reward=1.0,
            next_observation={"test": "next"},
            done=False,
            timestamp=123.0
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "test.json"
            transition.save(str(filepath))
            
            loaded = WorldModelTransition.load(str(filepath))
            self.assertEqual(loaded.action, transition.action)
            self.assertEqual(loaded.reward, transition.reward)
    
    def test_dataset_operations(self):
        """测试数据集操作"""
        dataset = WorldModelDataset()
        
        # 添加样本
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
        
        self.assertEqual(len(dataset), 2)
        self.assertIn("click", dataset.skill_vocab)
        self.assertIn("type", dataset.skill_vocab)
        
        # 采样
        samples = dataset.sample(1)
        self.assertEqual(len(samples), 1)
    
    def test_dataset_statistics(self):
        """测试数据集统计"""
        dataset = WorldModelDataset()
        
        for i in range(10):
            dataset.add(
                observation={"test": f"data{i}"},
                action="click" if i % 2 == 0 else "type",
                reward=float(i)
            )
        
        stats = dataset.get_statistics()
        self.assertEqual(stats["total_transitions"], 10)
        self.assertEqual(stats["unique_skills"], 2)
        self.assertAlmostEqual(stats["average_reward"], 4.5, places=1)


class TestObservationEncoder(unittest.TestCase):
    """测试观察编码器"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = EncoderConfig(latent_dim=64)
        self.encoder = SimpleObservationEncoder(self.config)
    
    def test_encode_simple(self):
        """测试简单编码"""
        observation = {
            "window_title": "Notepad",
            "active_app": "notepad.exe",
            "cursor_pos": (100, 200)
        }
        
        latent = self.encoder.encode(observation)
        self.assertEqual(latent.shape, (64,))
    
    def test_encode_with_screenshot(self):
        """测试带截图的编码"""
        observation = {
            "screenshot": np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8),
            "window_title": "Notepad",
            "active_app": "notepad.exe",
            "cursor_pos": (100, 200)
        }
        
        latent = self.encoder.encode(observation)
        self.assertEqual(latent.shape, (64,))
    
    def test_encode_batch(self):
        """测试批量编码"""
        observations = [
            {"window_title": "App1", "active_app": "app1.exe", "cursor_pos": (0, 0)},
            {"window_title": "App2", "active_app": "app2.exe", "cursor_pos": (100, 100)},
        ]
        
        latents = self.encoder.encode_batch(observations)
        self.assertEqual(latents.shape, (2, 64))
    
    def test_cache(self):
        """测试缓存功能"""
        encoder = SimpleObservationEncoder(
            EncoderConfig(cache_encodings=True)
        )
        
        observation = {"window_title": "Test", "active_app": "test.exe", "cursor_pos": (0, 0)}
        
        # 第一次编码
        latent1 = encoder.encode(observation)
        # 第二次编码（应使用缓存）
        latent2 = encoder.encode(observation)
        
        np.testing.assert_array_equal(latent1, latent2)


class TestDynamicsModel(unittest.TestCase):
    """测试动态模型"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = DynamicsConfig(
            input_dim=192,  # 128 (state) + 64 (action)
            output_dim=128,
            num_ensembles=3
        )
        self.model = DynamicsModel(self.config)
    
    def test_predict(self):
        """测试预测"""
        state = np.random.randn(128)
        action = np.random.randn(64)
        
        next_state, uncertainty = self.model.predict(state, action)
        
        self.assertEqual(next_state.shape, (128,))
        self.assertGreater(uncertainty, 0)
    
    def test_predict_batch(self):
        """测试批量预测"""
        states = np.random.randn(5, 128)
        actions = np.random.randn(5, 64)
        
        next_states, uncertainties = self.model.predict_batch(states, actions)
        
        self.assertEqual(next_states.shape, (5, 128))
        self.assertEqual(uncertainties.shape, (5,))
    
    def test_train(self):
        """测试训练"""
        # 生成假数据
        dataset = []
        for _ in range(100):
            state = np.random.randn(128)
            action = np.random.randn(64)
            next_state = state + np.random.randn(128) * 0.1  # 小变化
            dataset.append((state, action, next_state))
        
        # 训练（短时间）
        self.model.train(dataset, epochs=5)
        
        # 验证预测能力
        test_state = np.random.randn(128)
        test_action = np.random.randn(64)
        next_state, _ = self.model.predict(test_state, test_action)
        
        self.assertIsNotNone(next_state)


class TestRewardModel(unittest.TestCase):
    """测试奖励模型"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = RewardConfig(input_dim=128, hidden_dim=64)
        self.model = RewardModel(self.config)
    
    def test_predict(self):
        """测试预测"""
        state = np.random.randn(128)
        reward = self.model.predict(state)
        
        self.assertIsInstance(reward, (int, float))
    
    def test_predict_batch(self):
        """测试批量预测"""
        states = np.random.randn(10, 128)
        rewards = self.model.predict_batch(states)
        
        self.assertEqual(rewards.shape, (10,))
    
    def test_train(self):
        """测试训练"""
        # 生成假数据
        dataset = []
        for _ in range(100):
            state = np.random.randn(128)
            reward = np.random.randn()  # 随机奖励
            dataset.append((state, reward))
        
        # 训练
        self.model.train(dataset, epochs=5)
        
        # 验证预测能力
        test_state = np.random.randn(128)
        reward = self.model.predict(test_state)
        
        self.assertIsNotNone(reward)


class TestLatentPlanner(unittest.TestCase):
    """测试规划器"""
    
    def setUp(self):
        """设置测试环境"""
        self.world_model = WorldModel(
            WorldModelConfig(
                encoder_config=EncoderConfig(latent_dim=64),
                action_embedding_dim=32
            )
        )
        self.planner = LatentPlanner(
            self.world_model,
            PlannerConfig(
                horizon=5,
                num_candidates=10
            )
        )
    
    def test_plan(self):
        """测试规划"""
        state = np.random.randn(64)
        actions = ["click", "type", "scroll"]
        
        best_action, expected_return, sequence = self.planner.plan(
            state,
            actions,
            horizon=3
        )
        
        self.assertIn(best_action, actions)
        self.assertEqual(len(sequence), 3)
    
    def test_random_shooting(self):
        """测试随机打靶"""
        planner = LatentPlanner(
            self.world_model,
            PlannerConfig(
                horizon=5,
                num_candidates=20,
                planning_method="random_shooting"
            )
        )
        
        state = np.random.randn(64)
        actions = ["click", "type"]
        
        best_action, _, _ = planner.plan(state, actions)
        self.assertIn(best_action, actions)


class TestWorldModel(unittest.TestCase):
    """测试世界模型"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = WorldModelConfig(
            encoder_config=EncoderConfig(latent_dim=64),
            action_embedding_dim=32
        )
        self.model = WorldModel(self.config)
    
    def test_encode_observation(self):
        """测试观察编码"""
        observation = {
            "window_title": "Notepad",
            "active_app": "notepad.exe",
            "cursor_pos": (100, 200)
        }
        
        state = self.model.encode_observation(observation)
        self.assertEqual(state.shape, (64,))
    
    def test_predict_next_state(self):
        """测试下一状态预测"""
        state = np.random.randn(64)
        action = "click"
        
        next_state, uncertainty = self.model.predict_next_state(state, action)
        
        self.assertEqual(next_state.shape, (64,))
        self.assertGreater(uncertainty, 0)
    
    def test_imagine_rollout(self):
        """测试想象回放"""
        state = np.random.randn(64)
        action_sequence = ["click", "type", "scroll"]
        
        states, rewards, uncertainties = self.model.imagine_rollout(
            state,
            action_sequence
        )
        
        self.assertEqual(len(states), 4)  # 初始 + 3 步
        self.assertEqual(len(rewards), 4)
        self.assertEqual(len(uncertainties), 4)
    
    def test_collect_training_data(self):
        """测试训练数据收集"""
        observations = [
            {"window_title": "App1", "active_app": "app1.exe", "cursor_pos": (0, 0)},
            {"window_title": "App2", "active_app": "app2.exe", "cursor_pos": (100, 100)},
        ]
        actions = ["click", "type"]
        rewards = [1.0, 0.5]
        
        dataset = self.model.collect_training_data(
            observations,
            actions,
            rewards
        )
        
        self.assertEqual(len(dataset), 2)
    
    def test_train_and_evaluate(self):
        """测试训练和评估"""
        # 生成训练数据
        observations = [
            {"window_title": f"App{i}", "active_app": f"app{i}.exe", "cursor_pos": (i * 10, i * 10)}
            for i in range(20)
        ]
        actions = ["click", "type", "scroll"] * 6 + ["click", "type"]
        rewards = [np.random.randn() for _ in range(20)]
        
        dataset = self.model.collect_training_data(
            observations,
            actions,
            rewards
        )
        
        # 训练（短时间）
        self.model.train(dataset, epochs_dynamics=5, epochs_reward=5)
        
        # 评估
        metrics = self.model.evaluate(dataset, num_samples=10)
        self.assertIn("dynamics_mse", metrics)
        self.assertIn("reward_mse", metrics)
    
    def test_save_and_load(self):
        """测试保存和加载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 训练模型
            observations = [
                {"window_title": f"App{i}", "active_app": f"app{i}.exe", "cursor_pos": (i * 10, i * 10)}
                for i in range(10)
            ]
            actions = ["click", "type"] * 5
            dataset = self.model.collect_training_data(observations, actions)
            self.model.train(dataset, epochs_dynamics=3, epochs_reward=3)
            
            # 保存
            save_path = Path(tmpdir) / "test_model"
            self.model.save(str(save_path))
            
            # 加载
            loaded_model = WorldModel.load(str(save_path))
            
            # 验证
            test_obs = {"window_title": "Test", "active_app": "test.exe", "cursor_pos": (0, 0)}
            state1 = self.model.encode_observation(test_obs)
            state2 = loaded_model.encode_observation(test_obs)
            
            # 编码结果应该相似（可能有随机性）
            np.testing.assert_array_equal(state1.shape, state2.shape)


class TestWorldModelTrainer(unittest.TestCase):
    """测试世界模型训练器"""
    
    def setUp(self):
        """设置测试环境"""
        with tempfile.TemporaryDirectory() as tmpdir:
            self.tmpdir = Path(tmpdir)
        
        self.world_model = WorldModel(
            WorldModelConfig(
                encoder_config=EncoderConfig(latent_dim=64),
                action_embedding_dim=32
            )
        )
        self.trainer = WorldModelTrainer(
            self.world_model,
            checkpoint_dir=str(self.tmpdir / "checkpoints")
        )
    
    def test_train(self):
        """测试训练"""
        # 生成训练数据
        observations = [
            {"window_title": f"App{i}", "active_app": f"app{i}.exe", "cursor_pos": (i * 10, i * 10)}
            for i in range(30)
        ]
        actions = ["click", "type", "scroll"] * 10
        rewards = [np.random.randn() for _ in range(30)]
        
        train_dataset = self.world_model.collect_training_data(
            observations,
            actions,
            rewards
        )
        
        # 训练
        history = self.trainer.train(
            train_dataset,
            num_epochs=2,
            epochs_dynamics=2,
            epochs_reward=2,
            eval_interval=1,
            save_interval=10
        )
        
        self.assertIn("epochs", history)
        self.assertIn("train_metrics", history)


def run_tests():
    """运行所有测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加所有测试
    suite.addTests(loader.loadTestsFromTestCase(TestWorldModelData))
    suite.addTests(loader.loadTestsFromTestCase(TestObservationEncoder))
    suite.addTests(loader.loadTestsFromTestCase(TestDynamicsModel))
    suite.addTests(loader.loadTestsFromTestCase(TestRewardModel))
    suite.addTests(loader.loadTestsFromTestCase(TestLatentPlanner))
    suite.addTests(loader.loadTestsFromTestCase(TestWorldModel))
    suite.addTests(loader.loadTestsFromTestCase(TestWorldModelTrainer))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回测试结果
    return result


if __name__ == "__main__":
    result = run_tests()
    
    # 打印摘要
    print("\n" + "=" * 70)
    print("测试摘要")
    print("=" * 70)
    print(f"运行测试: {result.testsRun}")
    print(f"成功: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 部分测试失败")
        exit(1)
