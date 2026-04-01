# 世界模型融合设计方案

**日期**: 2026-04-01  
**版本**: 1.0  
**作者**: CodeBuddy AI Assistant

---

## 一、世界模型核心理论

### 1.1 杨立昆世界模型的核心思想

**世界模型（World Model）**是 Yann LeCun 提出的通用人工智能框架，旨在让智能体像人类一样理解、预测和规划与环境的交互。

**核心原理**:
1. **联合嵌入预测架构（JEPA）**: 不是重建原始输入，而是在潜在空间中预测未来状态
2. **自监督学习**: 从观察序列中学习环境动态，无需显式奖励信号
3. **分层规划**: 通过想象/模拟来评估动作序列，减少真实交互成本
4. **不确定性估计**: 预测时建模不确定性，避免过度自信

**优势**:
- 样本效率高（减少真实交互）
- 适应环境变化（泛化能力强）
- 安全性（先模拟后执行）
- 长期规划能力

### 1.2 JEPA 关键技术

**数学形式**:
```
p(s_{t+1} | s_t, a_t)
```
给定当前状态 `s_t` 和动作 `a_t`，预测下一个状态 `s_{t+1}`。

**核心组件**:
1. **表征模型（Encoder）**: 将高维观察映射到低维潜在空间
2. **动态模型（Dynamics）**: 在潜在空间中预测未来状态
3. **奖励模型（Reward）**: 预测给定状态的预期奖励
4. **策略网络（Policy）**: 基于模型预测进行决策

**代表性工作**:
- **Dreamer V2/V3**: 端到端训练，在潜在空间中学习和规划
- **V-JEPA 2**: 视觉世界模型，用于机器人控制
- **LeWorldModel**: 端到端 JEPA，从像素直接训练（2026最新）

---

## 二、NovaHands 现有架构分析

### 2.1 现有能力

**RL 系统**:
- `rl/environment.py`: Gymnasium 环境封装
- `rl/collector.py`: 经验收集器（支持多线程）
- `rl/trainer.py**: PPO 训练器（支持 LoRA 微调）
- `rl/policy.py`: 策略网络（Transformer 架构）

**学习系统**:
- `learning/action_recorder.py`: 动作录制
- `learning/action_replayer.py`: 任务回放（OpenAdapt 风格）
- `learning/pattern_miner.py`: 行为模式挖掘
- `learning/skill_generator.py`: 自动生成技能

**记忆系统**:
- `core/executor_memory.py`: 执行历史、错误模式检测、上下文摘要

### 2.2 当前局限性

1. **样本效率低**: RL 训练需要大量真实交互
2. **缺乏世界模型**: 无环境预测能力，无法规划
3. **经验浪费**: 回放数据仅用于监督学习，未用于模型学习
4. **泛化能力弱**: 难以适应 UI 变化和新应用

---

## 三、世界模型融合方案设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    NovaHands Core                      │
│  ┌──────────────┐      ┌──────────────┐               │
│  │  NL Executor │◄────►│  Skill Mgr   │               │
│  └──────────────┘      └──────────────┘               │
│           │                     │                      │
│           ▼                     ▼                      │
│  ┌──────────────────────────────────────────┐         │
│  │     World Model Module (NEW)             │         │
│  │  ┌─────────┐  ┌─────────┐  ┌────────┐ │         │
│  │  │ Encoder │  │ Dynamics│  │ Reward │ │         │
│  │  │         │  │         │  │ Model  │ │         │
│  │  └────┬────┘  └────┬────┘  └────┬───┘ │         │
│  │       │             │             │     │         │
│  │       ▼             ▼             ▼     │         │
│  │  ┌──────────────────────────────┐      │         │
│  │  │    Latent Planner (MPC)    │      │         │
│  │  └──────────────────────────────┘      │         │
│  └──────────────────────────────────────────┘         │
│           ▲                     ▲                      │
│           │                     │                      │
│  ┌────────┴──────┐    ┌──────┴────────┐            │
│  │ RL Trainer    │    │ Action Replay │            │
│  │ (PPO + Dreamer│    │ + Simulation  │            │
│  │  style)       │    │               │            │
│  └───────────────┘    └───────────────┘            │
└─────────────────────────────────────────────────────────┘
```

### 3.2 核心模块设计

#### 3.2.1 表征模型（Encoder）

**文件**: `world_model/encoder.py`

**功能**:
- 将桌面环境观察编码为潜在向量
- 支持多模态输入（屏幕截图、窗口标题、文件状态等）

**实现思路**:
```python
class ObservationEncoder:
    def encode(self, observation: Dict[str, Any]) -> np.ndarray:
        """
        编码桌面观察
        
        Parameters
        ----------
        observation : dict
            {
                "screenshot": np.ndarray (H, W, 3),
                "window_title": str,
                "active_app": str,
                "cursor_pos": (x, y),
                "file_changes": List[str]
            }
        
        Returns
        -------
        latent_vector : np.ndarray (latent_dim,)
        """
        # 屏幕特征提取（轻量级 CNN，如 MobileNet）
        screen_features = self._encode_screenshot(observation["screenshot"])
        
        # 语义特征（窗口标题、应用名）
        text_features = self._encode_text(
            observation["window_title"],
            observation["active_app"]
        )
        
        # 拼接并投影
        combined = np.concatenate([screen_features, text_features])
        latent = self.projection_head(combined)
        return latent
```

**设计决策**:
- 使用轻量级 CNN（避免 GPU 依赖）
- 文本特征可使用预训练模型（如 sentence-transformers）或简单 Embedding
- 潜在维度：64-128（平衡表达能力和计算成本）

#### 3.2.2 动态模型（Dynamics）

**文件**: `world_model/dynamics.py`

**功能**:
- 预测潜在状态转移 `s_{t+1} = f(s_t, a_t)`
- 估计预测不确定性

**实现思路**:
```python
class DynamicsModel:
    def predict(
        self,
        current_state: np.ndarray,
        action: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        预测下一个状态及其不确定性
        
        Returns
        -------
        next_state : np.ndarray
            预测的潜在状态
        uncertainty : np.ndarray
            预测不确定性（熵或方差）
        """
        # 使用小型神经网络（MLP 或 Transformer）
        latent_diff = self.transition_net(
            np.concatenate([current_state, action])
        )
        
        next_state = current_state + latent_diff
        
        # 不确定性估计（使用集成学习或贝叶斯方法）
        uncertainty = self._estimate_uncertainty(current_state, action)
        
        return next_state, uncertainty
```

**设计决策**:
- 集成学习（3-5 个模型）估计不确定性
- 训练目标：MSE + 预测熵损失
- 支持多步预测（rollout）

#### 3.2.3 奖励模型（Reward）

**文件**: `world_model/reward.py`

**功能**:
- 预测给定潜在状态的预期奖励
- 支持稀疏奖励的泛化

**实现思路**:
```python
class RewardModel:
    def predict_reward(self, state: np.ndarray) -> float:
        """
        预测状态价值
        """
        return self.reward_head(state)
```

#### 3.2.4 潜在规划器（Planner）

**文件**: `world_model/planner.py`

**功能**:
- 在潜在空间中执行模型预测控制（MPC）
- 评估动作序列并选择最优动作

**实现思路**:
```python
class LatentPlanner:
    def plan(
        self,
        current_state: np.ndarray,
        horizon: int = 10,
        num_candidates: int = 100
    ) -> np.ndarray:
        """
        在潜在空间中规划最优动作序列
        
        Returns
        -------
        best_action : np.ndarray
            下一步最优动作
        """
        # 随机采样或交叉熵方法（CEM）生成候选序列
        action_sequences = self._sample_action_sequences(
            horizon, num_candidates
        )
        
        # 在世界模型中模拟每个序列
        returns = []
        for actions in action_sequences:
            state = current_state
            total_reward = 0
            for a in actions:
                state, uncertainty = self.dynamics.predict(state, a)
                reward = self.reward.predict_reward(state)
                # 惩罚高不确定性
                reward -= self.uncertainty_weight * uncertainty
                total_reward += reward
            returns.append(total_reward)
        
        # 选择最佳序列的第一个动作
        best_idx = np.argmax(returns)
        best_action = action_sequences[best_idx][0]
        
        return best_action
```

**设计决策**:
- 规划视野：5-20 步（权衡效率和效果）
- 不确定性惩罚：避免在未知区域过度自信
- 可选择随机打靶或 CEM 优化

---

### 3.3 训练流程

#### 3.3.1 数据收集

**来源**:
1. **RL 训练数据**: `(observation, action, reward, next_observation)`
2. **任务回放数据**: `action_replayer.py` 录制的动作序列
3. **用户交互日志**: `executor_memory.py` 执行历史

**数据格式**:
```python
@dataclass
class WorldModelTransition:
    observation: Dict[str, Any]
    action: str  # 技能名称或嵌入
    reward: float
    next_observation: Dict[str, Any]
    done: bool
    timestamp: float
```

#### 3.3.2 训练阶段

**阶段 1: 表征学习（自监督）**
- 目标：学习有意义的观察表示
- 方法：对比学习（SimCLR 风格）或 JEPA
- 损失：`L_jepa`（联合嵌入预测损失）

**阶段 2: 动态学习**
- 目标：学习环境动态转移
- 方法：监督学习 `(s_t, a_t) -> s_{t+1}`
- 损失：`L_dynamics = MSE(s_{t+1}, pred_s_{t+1})`

**阶段 3: 奖励学习**
- 目标：预测状态价值
- 方法：监督学习 `s -> r`
- 损失：`L_reward = MSE(r, pred_r)`

**阶段 4: 端到端微调**
- 目标：优化整体性能
- 方法：Dreamer 风格联合训练
- 损失：`L_total = L_dynamics + λ_reward * L_reward + λ_jepa * L_jepa`

#### 3.3.3 训练策略

**样本效率优化**:
1. **离线预训练**: 先用历史数据训练世界模型
2. **在线微调**: RL 过程中持续更新模型
3. **重放缓冲区**: 存储多样性经验

**不确定性感知**:
1. **集成学习**: 训练多个动态模型
2. **数据增强**: 随机遮挡、噪声注入
3. **早停策略**: 不确定性过高时停止预测

---

### 3.4 与现有系统集成

#### 3.4.1 集成到 RL 系统

**修改**: `rl/trainer.py`

```python
class DreamerStyleTrainer(PPOTrainer):
    def __init__(self, world_model, **kwargs):
        super().__init__(**kwargs)
        self.world_model = world_model
    
    def collect_experience(self, env, policy, num_steps):
        # 真实环境采样（少量）
        real_data = super().collect_experience(env, policy, num_steps // 4)
        
        # 梦境采样（大量）
        dream_data = self.world_model.imagine_rollouts(
            policy,
            num_steps * 3  # 3:1 梦境:真实比例
        )
        
        # 合并数据
        return real_data + dream_data
```

**优势**:
- 减少 75% 真实交互
- 训练速度提升 3-5 倍
- 策略泛化能力增强

#### 3.4.2 集成到任务回放

**修改**: `learning/action_replayer.py`

```python
class ActionReplayerWithWorldModel(ActionReplayer):
    def __init__(self, safe_guard, world_model, **kwargs):
        super().__init__(safe_guard, **kwargs)
        self.world_model = world_model
    
    def validate_sequence(self, steps: List[ReplayStep]) -> bool:
        """
        在世界模型中模拟整个动作序列，验证可行性
        """
        # 初始状态（当前屏幕）
        current_state = self.world_model.encode_observation(
            self.get_current_observation()
        )
        
        for step in steps:
            # 预测执行后的状态
            action = self._step_to_action(step)
            next_state, uncertainty = self.world_model.dynamics.predict(
                current_state, action
            )
            
            # 如果不确定性过高，拒绝回放
            if uncertainty > self.uncertainty_threshold:
                return False
            
            current_state = next_state
        
        return True
```

**优势**:
- 预先验证回放安全性
- 避免破坏性操作
- 提升回放成功率

#### 3.4.3 集成到自然语言执行器

**修改**: `core/nl_executor.py`

```python
class NLExecutorWithWorldModel(NLExecutor):
    def __init__(self, world_model, **kwargs):
        super().__init__(**kwargs)
        self.world_model = world_model
    
    def execute(self, user_input: str):
        # 解析用户意图
        skill_call = self.parse_intent(user_input)
        
        # 如果是复杂任务，使用世界模型规划
        if self._is_complex_task(skill_call):
            skill_call = self.world_model.plan_skill_sequence(
                skill_call, user_input
            )
        
        # 执行
        return super().execute(skill_call)
```

---

### 3.5 实施计划

#### 阶段 1: 基础实现（1-2 周）

**目标**: 实现核心模块，验证可行性

**任务**:
1. 创建 `world_model/` 目录
2. 实现 `encoder.py`（轻量级）
3. 实现 `dynamics.py`（MLP）
4. 实现基础测试

**交付物**:
- `world_model/encoder.py`
- `world_model/dynamics.py`
- `tests/test_world_model.py`

#### 阶段 2: 训练集成（2-3 周）

**目标**: 训练世界模型，集成到 RL 系统

**任务**:
1. 实现数据收集器
2. 训练动态模型和奖励模型
3. 修改 `rl/trainer.py` 支持梦境采样
4. 验证样本效率提升

**交付物**:
- `world_model/trainer.py`
- `rl/trainer.py` (Dreamer 风格)
- 训练好的模型权重

#### 阶段 3: 规划与回放（2-3 周）

**目标**: 实现潜在规划和回放验证

**任务**:
1. 实现 `planner.py`
2. 集成到 `action_replayer.py`
3. 验证安全性提升

**交付物**:
- `world_model/planner.py`
- `learning/action_replayer.py` (增强版)

#### 阶段 4: 自然语言集成（1-2 周）

**目标**: 增强自然语言执行器

**任务**:
1. 修改 `nl_executor.py`
2. 实现任务规划逻辑
3. 验证复杂任务处理

**交付物**:
- `core/nl_executor.py` (增强版)

#### 阶段 5: 测试与优化（1-2 周）

**目标**: 全面测试和性能优化

**任务**:
1. 编写完整测试套件
2. 性能基准测试
3. 文档编写

**交付物**:
- `tests/test_world_model_integration.py`
- `docs/WORLD_MODEL_GUIDE.md`
- 性能报告

---

## 四、技术挑战与解决方案

### 4.1 挑战 1: 屏幕特征提取

**问题**:
- 桌面环境高分辨率（1920x1080+）
- 直接使用 CNN 计算开销大

**解决方案**:
- 下采样到 64x64 或 128x128
- 使用轻量级 CNN（MobileNetV2）
- 仅截取感兴趣区域（ROI）
- 缓存编码结果

### 4.2 挑战 2: 动作空间离散化

**问题**:
- 技能数量动态变化（用户可自定义）
- 动作空间不稳定

**解决方案**:
- 使用技能嵌入（learned embedding）
- 支持新技能的增量学习
- 动作空间归一化

### 4.3 挑战 3: 部分可观性

**问题**:
- 屏幕无法显示所有信息（后台进程、文件状态）
- 隐藏状态难以建模

**解决方案**:
- 扩展观察空间（包括窗口列表、文件系统快照）
- 使用循环网络（RNN/Transformer）编码历史
- 学习推断隐藏状态

### 4.4 挑战 4: 模型偏差累积

**问题**:
- 多步预测误差累积
- 长期规划不可靠

**解决方案**:
- 限制规划视野（10 步以内）
- 不确定性加权
- 混合真实和梦境数据

---

## 五、预期收益

### 5.1 样本效率

- **目标**: 减少 60-80% 真实交互
- **指标**: 达到相同性能所需的步数

### 5.2 安全性

- **目标**: 回放验证成功率提升 40%
- **指标**: 破坏性操作减少

### 5.3 泛化能力

- **目标**: 适应新应用的速度提升 3-5 倍
- **指标**: 新应用的冷启动步数

### 5.4 长期规划

- **目标**: 支持多步骤复杂任务
- **指标**: 多任务完成率

---

## 六、风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 训练不稳定 | 中 | 高 | 使用 JEPA、集成学习 |
| 计算开销大 | 中 | 中 | 轻量级模型、缓存 |
| 过拟合历史数据 | 中 | 中 | 数据增强、正则化 |
| 与现有系统不兼容 | 低 | 高 | 渐进式集成、充分测试 |
| 用户不接受 | 低 | 中 | 保留传统方法、可配置 |

---

## 七、成功标准

### 最小可行产品（MVP）

1. ✅ 实现基础的编码器和动态模型
2. ✅ 训练出能预测 5 步的模型（误差 < 20%）
3. ✅ 集成到 RL 训练器，减少 30% 真实交互
4. ✅ 通过所有测试

### 完整产品

1. ✅ 实现完整的 JEPA 架构
2. ✅ 支持 20 步规划（不确定性 < 30%）
3. ✅ 集成到任务回放和 NL 执行器
4. ✅ 样本效率提升 60%+
5. ✅ 性能报告和完整文档

---

## 八、参考资料

1. **LeCun, Y. et al.** (2022). "A Path Towards Autonomous Machine Intelligence"
2. **Danijar Hafner et al.** (2020). "Dream to Control: Learning Behaviors without Raw Rewards" (Dreamer)
3. **Danijar Hafner et al.** (2023). "Mastering Diverse Domains through World Models" (DreamerV3)
4. **Lucas Maes et al.** (2026). "LeWorldModel: Stable End-to-End Joint-Embedding Predictive Architecture from Pixels"
5. **V-JEPA 2** (2025). Vision-based world modeling for embodied AI

---

## 九、附录

### A. 配置文件示例

`config/wold_model.json`:
```json
{
  "encoder": {
    "screen_size": [64, 64],
    "latent_dim": 128,
    "text_embedding_dim": 32,
    "cache_encodings": true
  },
  "dynamics": {
    "num_ensembles": 5,
    "hidden_dim": 256,
    "activation": "gelu"
  },
  "planner": {
    "horizon": 10,
    "num_candidates": 100,
    "uncertainty_weight": 0.1
  },
  "training": {
    "batch_size": 64,
    "learning_rate": 1e-4,
    "dream_to_real_ratio": 3
  }
}
```

### B. 关键类接口

```python
# world_model/base.py
class WorldModel(ABC):
    @abstractmethod
    def encode_observation(self, obs: Dict) -> np.ndarray:
        pass
    
    @abstractmethod
    def predict_next_state(
        self,
        state: np.ndarray,
        action: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        pass
    
    @abstractmethod
    def plan(
        self,
        current_state: np.ndarray,
        horizon: int
    ) -> np.ndarray:
        pass
```

---

**文档版本**: 1.0  
**最后更新**: 2026-04-01
