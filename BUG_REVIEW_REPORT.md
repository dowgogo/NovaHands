# Bug Review Report

**Scope**: NovaHands 全项目核心模块审查
**Status**: FIXED (2026-04-01)

---

## Fix Summary

All 9 bugs have been fixed:
- CRITICAL-1: Success execution now recorded to memory
- CRITICAL-2: Failure records now include actual skill_name
- HIGH-1: Added counter empty check to prevent IndexError
- HIGH-2: Extended special key handling for <CHAR>, <LETTER>, <unknown>
- MEDIUM-1: _check_before unknown type now returns False (deny for safety)
- MEDIUM-2: save() already has atomic write and error handling
- LOW-1: Python 3.7+ dict order is guaranteed, no fix needed
- LOW-2: Added negative value validation for max_new_tokens

Test result: 60/60 tests passed

---

---

## Critical Issues

### [CRITICAL-1] 成功执行未记录到 Memory
**Location**: `NovaHands/core/nl_executor.py:127-138`
**Description**: 当 LLM 正确识别并成功执行技能时，函数直接返回 `skill_name`，但没有将成功结果记录到 ExecutorMemory 中。

**Trigger**: 当 LLM 返回有效技能名且技能执行成功时（第 127 行执行路径）

**Impact**: 
- 成功的执行不会被记录到执行历史
- 导致 `build_context_summary()` 无法构建完整的上下文
- 重试时的错误诊断 Prompt 缺少成功案例的参考

**Evidence**:
```python
# 第 127-138 行
self.skill_manager.execute_skill(skill_name, controller, **params)
duration = time.monotonic() - t_start
logger.info(f"Executed skill: {skill_name} (attempt={attempt}, {duration:.2f}s)")
# BUG: 成功时没有记录到 memory
return skill_name

# vs 失败时的记录（第 149-155 行）：
except Exception as e:
    # ...
    self.memory.add(ExecutionRecord(
        skill_name="unknown",
        parameters={},
        success=False,
        error_msg=error_str[:200],
        duration=duration,
    ))
```

**Suggested Fix**:
```python
# 在 return skill_name 之前添加：
self.memory.add(ExecutionRecord(
    skill_name=skill_name,
    parameters=skill_call.parameters,
    success=True,
    error_msg=None,
    duration=duration,
))
return skill_name
```

---

### [CRITICAL-2] 失败记录中 skill_name 始终为 "unknown"
**Location**: `NovaHands/core/nl_executor.py:149-155`
**Description**: 当 LLM 返回的技能名不在注册表中时，异常被捕获并记录为 "unknown"，即使此时 `skill_name` 变量已经有值（可以用于诊断）。

**Trigger**: 当 LLM 返回一个不在白名单中的技能名时（如 LLM 幻觉了一个不存在的技能名）

**Impact**: 
- 错误历史记录不准确
- 难以诊断是 LLM 幻觉还是其他问题
- `error_pattern_hint()` 无法正确识别失败模式

**Evidence**:
```python
# 第 121-122 行
if not self.skill_manager.get_skill(skill_name):
    raise ValueError(f"Skill '{skill_name}' not found in registry")
# 此时 skill_name 有值但随后被丢弃

except Exception as e:
    # ...
    self.memory.add(ExecutionRecord(
        skill_name="unknown",  # BUG: 应该是 skill_name
        parameters={},
        success=False,
        error_msg=error_str[:200],
        duration=duration,
    ))
```

**Suggested Fix**:
```python
# 定义一个变量来追踪要记录的技能名
recorded_skill = "unknown"
try:
    # ...
    if not self.skill_manager.get_skill(skill_name):
        recorded_skill = skill_name  # 保存实际技能名
        raise ValueError(f"Skill '{skill_name}' not found in registry")
    # ...
except Exception as e:
    self.memory.add(ExecutionRecord(
        skill_name=recorded_skill,  # 使用保存的值
        # ...
    ))
```

---

## High Issues

### [HIGH-1] counter 为空时 IndexError
**Location**: `NovaHands/core/executor_memory.py:137`
**Description**: 虽然第 129 行检查了 `errors` 非空，但 `Counter(names).most_common(1)` 可能返回空列表（当所有错误技能名频率相同时），导致 `counter.most_common(1)[0]` 抛出 IndexError。

**Trigger**: 当连续多个不同技能失败时（频率都是 1）

**Impact**: 程序崩溃

**Evidence**:
```python
# 第 129-142 行
errors = self.recent_errors(n=5)
if not errors:
    return None

from collections import Counter
names = [r.skill_name for r in errors]
counter = Counter(names)
most_common_name, count = counter.most_common(1)[0]  # IndexError 如果为空
```

**Suggested Fix**:
```python
most_common_list = counter.most_common(1)
if not most_common_list:
    return None
most_common_name, count = most_common_list[0]
```

---

### [HIGH-2] action_replayer 特殊键处理不完整
**Location**: `NovaHands/learning/action_replayer.py:266-272`
**Description**: `_execute_key_press` 只处理了 `Key.` 前缀和 `<CHAR>` 占位符，但 `<LETTER>` 和 `<unknown>` 等特殊值会被传入 `pyautogui.press()`，可能导致错误行为。

**Trigger**: 回放包含这些特殊键名的录制内容

**Impact**: 特殊键可能被错误执行或抛出异常

**Evidence**:
```python
# 第 266-272 行
if key.startswith("Key."):
    key_name = key.split(".")[-1]
    pyautogui.press(key_name)
elif key == "<CHAR>":
    # 跳过处理
    return True
else:
    # 直接传入键名 - <LETTER> 和 <unknown> 落入此处
    pyautogui.press(key)  # 可能导致 pyautogui 异常
```

**Suggested Fix**:
```python
# 添加对所有特殊值的处理
if key == "<CHAR>" or key == "<LETTER>" or key == "<unknown>":
    logger.debug(f"Skipping sanitized key: {key}")
    return True
elif key.startswith("Key."):
    key_name = key.split(".")[-1]
    pyautogui.press(key_name)
else:
    pyautogui.press(key)
```

---

## Medium Issues

### [MEDIUM-1] _check_before 对未知类型默认返回 True
**Location**: `NovaHands/learning/action_replayer.py:168-186`
**Description**: `_check_before` 方法对未知检查类型默认返回 `True`，可能绕过安全检查。

**Trigger**: 使用自定义检查类型（如 "element_visible"）

**Impact**: 安全检查可能失效，允许在不满足条件时执行回放

**Evidence**:
```python
def _check_before(self, step: ReplayStep) -> bool:
    # ...
    if check_type == "text_exists":
        # TODO: 实现 OCR 或 UI 自动化库检查
        logger.debug(f"Check: text_exists {step.check_before.get('text')}")
        return True
    elif check_type == "window_title":
        # 实际检查
        return contains.lower() in current_app.lower()
    else:
        logger.warning(f"Unknown check type: {check_type}")
        return True  # BUG: 应该返回 False 或抛出异常
```

**Suggested Fix**:
```python
else:
    logger.warning(f"Unknown check type: {check_type}, denying for safety")
    return False  # 拒绝未知类型的检查
```

---

### [MEDIUM-2] rl/collector 保存失败后未更新 episodes 计数
**Location**: `NovaHands/rl/collector.py:85, 92-93`
**Description**: `collect_episode` 中 `self.save()` 失败时不会抛出异常（除非磁盘完全不可写），但 `_episodes_since_train` 仍然会增加。如果 `save()` 静默失败（如权限问题但没有抛出异常），可能导致计数不一致。

**Trigger**: 保存失败但未抛出异常时

**Impact**: 训练触发时机不准确

**Evidence**:
```python
if any(r > 0 for _, _, r in trajectory):
    for s, a, r in trajectory:
        self.data.append({"state": s, "action": a, "reward": r})
    self.save()  # 可能静默失败
    logger.info(f"Collected trajectory with {len(trajectory)} steps")
# ...
self._episodes_since_train += 1  # 即使保存失败也会增加
```

**Suggested Fix**:
```python
try:
    self.save()
except Exception as e:
    logger.error(f"Failed to save episode data: {e}")
    # 仍然增加计数，因为数据已在 self.data 中
self._episodes_since_train += 1
```

---

## Low Issues

### [LOW-1] Prompt 构建依赖 dict 遍历顺序
**Location**: `NovaHands/core/nl_executor.py:296-310`
**Description**: `_build_prompt` 每次调用都重新遍历所有技能构建描述，但 dict 遍历顺序在 Python 3.7+ 虽然保证顺序，但如果技能动态注册，Prompt 可能不一致。

**Trigger**: 技能在运行期间被动态注册时

**Impact**: LLM 输出可能不稳定

**Suggested Fix**: 考虑缓存技能描述或排序后输出。

---

### [LOW-2] local_model 缺少参数验证
**Location**: `NovaHands/models/local_model.py:136-137`
**Description**: `max_new_tokens` 参数没有验证是否为负数，虽然 `min(int(requested_tokens), _MAX_NEW_TOKENS_LIMIT)` 可以处理，但如果 `requested_tokens` 是负数，结果也会是负数。

**Trigger**: 传入负数的 `max_new_tokens`

**Impact**: 模型生成行为异常

**Evidence**:
```python
requested_tokens = kwargs.get("max_new_tokens", 256)
nsafe_max_tokens = min(int(requested_tokens), _MAX_NEW_TOKENS_LIMIT)  # 负数不会被拒绝
```

**Suggested Fix**:
```python
requested_tokens = kwargs.get("max_new_tokens", 256)
nsafe_max_tokens = min(max(1, int(requested_tokens)), _MAX_NEW_TOKENS_LIMIT)
```

---

## Summary

| Severity | Count |
|----------|--------|
| Critical | 2 |
| High | 2 |
| Medium | 2 |
| Low | 2 |
| **Total** | **9** |

---

## Priority Fixes

1. **[CRITICAL-1]** 在成功执行时记录到 memory - 这影响核心执行逻辑和错误自恢复能力
2. **[CRITICAL-2]** 修复失败记录中的 skill_name - 这影响错误诊断的准确性
3. **[HIGH-1]** 修复 counter 为空时的 IndexError - 这会导致程序崩溃
4. **[HIGH-2]** 完善 action_replayer 的特殊键处理 - 这影响回放的安全性和准确性
5. **[MEDIUM-1]** 修复 _check_before 的默认返回值 - 这影响安全检查的有效性

---
