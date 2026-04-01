# 安全风险与代码优化报告

**Scope**: NovaHands 全项目安全审查（43 个 Python 源文件）
**Date**: 2026-04-01
**Status**: 发现 6 个安全问题 + 7 个优化建议

---

## 安全风险（需优先修复）

### [SEC-1] MCP 服务器缺少请求体大小限制
**Location**: `core/mcp_server.py:62-63`
**Severity**: HIGH
**Description**: POST `/mcp` 端点读取请求体时没有大小限制，恶意客户端可发送超大请求导致内存耗尽（DoS 攻击）。

**Evidence**:
```python
def do_POST(self):
    if self.path != "/mcp":
        self._send_json({"error": "Not found"}, status=404)
        return

    length = int(self.headers.get("Content-Length", 0))
    body = self.rfile.read(length)  # 无大小限制
```

**Impact**:
- 恶意客户端发送 `Content-Length: 999999999` 可耗尽服务器内存
- 导致服务崩溃或系统响应缓慢

**Suggested Fix**:
```python
# 添加最大请求体大小限制（例如 10MB）
_MAX_REQUEST_SIZE = 10 * 1024 * 1024

def do_POST(self):
    if self.path != "/mcp":
        self._send_json({"error": "Not found"}, status=404)
        return

    length = int(self.headers.get("Content-Length", 0))
    if length > _MAX_REQUEST_SIZE:
        self._send_json(
            {"error": f"Request too large (max {_MAX_REQUEST_SIZE} bytes)"},
            status=413
        )
        return
    body = self.rfile.read(length)
```

---

### [SEC-2] Recognizer 缺少模板路径验证（路径遍历风险）
**Location**: `core/recognizer.py:10-18`
**Severity**: MEDIUM
**Description**: `template_dir` 初始化时未验证路径合法性，用户传入含 `../` 的路径可访问任意目录。

**Evidence**:
```python
def __init__(self, template_dir: str = None):
    self.template_dir = template_dir or os.path.join(os.path.dirname(__file__), "..", "templates")
    if not os.path.exists(self.template_dir):
        os.makedirs(self.template_dir)  # 未验证路径合法性
```

**Impact**:
- 攻击者可访问或创建系统任意目录（需权限）
- 可能覆盖系统关键文件

**Suggested Fix**:
```python
def __init__(self, template_dir: str = None):
    raw_path = template_dir or os.path.join(os.path.dirname(__file__), "..", "templates")
    # 路径规范化，防止路径遍历
    self.template_dir = os.path.realpath(raw_path)
    # 可选：限制必须在项目目录下
    project_root = os.path.realpath(os.path.join(os.path.dirname(__file__), ".."))
    if not self.template_dir.startswith(project_root):
        raise ValueError(f"Template directory must be within project root: {self.template_dir}")

    if not os.path.exists(self.template_dir):
        os.makedirs(self.template_dir)
```

---

### [SEC-3] RLFineTuner.save_pretrained 未使用原子写入
**Location**: `rl/trainer.py:122-126`
**Severity**: MEDIUM
**Description**: 保存 LoRA 权重时直接写入，若训练中断可能导致文件损坏。

**Evidence**:
```python
self.output_dir.mkdir(parents=True, exist_ok=True)
self.lora_model.save_pretrained(str(self.output_dir))  # 非原子操作
```

**Impact**:
- 训练中断时权重文件可能不完整
- 重新加载时可能损坏或失败

**Suggested Fix**:
```python
import tempfile

# 使用临时目录 + 重命名实现原子写入
temp_dir = tempfile.mkdtemp(prefix="lora_weights_")
try:
    self.lora_model.save_pretrained(temp_dir)
    # 移动到目标位置（原子操作）
    import shutil
    if os.path.exists(self.output_dir):
        shutil.rmtree(self.output_dir)
    shutil.move(temp_dir, str(self.output_dir))
    logger.info(f"Training completed, LoRA weights saved to {self.output_dir}")
except Exception as e:
    logger.error(f"Failed to save LoRA weights: {e}")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    raise
```

---

### [SEC-4] evolution.py 技能名可能重复（UUID 前缀冲突）
**Location**: `rl/evolution.py:44`
**Severity**: LOW
**Description**: 使用 `uuid.uuid4().hex[:8]` 作为技能名，理论上 16^8 = 4.29 亿分之一概率冲突，但短时间多次调用仍有风险。

**Evidence**:
```python
skill_name = f"auto_{uuid.uuid4().hex[:8]}"
```

**Impact**:
- 技能名冲突时 `register_skill(..., overwrite=False)` 会跳过
- 丢失已生成的技能

**Suggested Fix**:
```python
# 使用完整 UUID 或增加长度（[:12] 降低冲突概率）
skill_name = f"auto_{uuid.uuid4().hex[:12]}"
# 或直接使用完整 UUID
# skill_name = f"auto_{uuid.uuid4().hex}"
```

---

### [SEC-5] OllamaModel.is_available 未验证响应内容
**Location**: `models/ollama_model.py:108-109`
**Severity**: LOW
**Description**: 健康检查只验证状态码，未验证 JSON 格式，可能误判服务可用。

**Evidence**:
```python
def is_available(self) -> bool:
    try:
        resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
        return resp.status_code == 200  # 未验证 JSON
    except Exception:
        return False
```

**Impact**:
- Ollama 服务崩溃返回 HTML 错误页时仍判为可用
- 后续调用时才失败

**Suggested Fix**:
```python
def is_available(self) -> bool:
    try:
        resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
        if resp.status_code != 200:
            return False
        # 验证 JSON 格式和包含 "models" 字段
        data = resp.json()
        return "models" in data
    except Exception:
        return False
```

---

### [SEC-6] API 执行锁未设置超时
**Location**: `api.py:12, 107-119`
**Severity**: MEDIUM
**Description**: `_execute_lock` 为全局锁，如果某个执行操作卡死（如死循环），所有后续请求都会永久阻塞。

**Evidence**:
```python
_execute_lock = asyncio.Lock()  # 无超时机制

async def execute(request: ExecuteRequest):
    async with _execute_lock:  # 可能永久阻塞
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: executor.execute(request.command, controller, **request.context)
        )
```

**Impact**:
- 单个恶意请求（如死循环脚本）可拖垮整个服务
- 正常请求也无法处理

**Suggested Fix**:
```python
async def execute(request: ExecuteRequest):
    executor = _resources.get('executor')
    controller = _resources.get('controller')
    if not executor or not controller:
        raise HTTPException(status_code=503, detail="Server not ready")

    # 使用 asyncio.wait_for 设置超时（例如 60 秒）
    try:
        async with _execute_lock:
            loop = asyncio.get_running_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: executor.execute(request.command, controller, **request.context)
                ),
                timeout=60.0  # 执行超时
            )
            return {"status": "success"}
    except asyncio.TimeoutError:
        logger.error(f"API execution timed out for command: {request.command}")
        raise HTTPException(status_code=408, detail="Execution timeout")
    except Exception as e:
        logger.error(f"API execution failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
```

---

## 代码优化建议（非安全问题）

### [OPT-1] MCPHandler.skill_manager 为类变量（线程安全问题）
**Location**: `core/mcp_server.py:42, 266-267`
**Description**: 使用类变量存储全局状态，HTTP 每个请求创建新 Handler 实例，但所有实例共享同一个 skill_manager，这在多线程环境下可能有问题。

**Suggested Fix**:
当前设计合理（HTTPServer 单线程处理请求），但建议添加注释说明：
```python
# 类变量：由 MCPServer.start() 注入，所有 Handler 实例共享
# 注意：HTTPServer 默认单线程，若改为多线程需使用 threading.local()
skill_manager = None
controller = None
```

---

### [OPT-2] ConfigLoader.get() 可优化为更安全的嵌套访问
**Location**: `utils/config_loader.py:59-69`
**Description**: 当前实现在非 dict 时返回 default，但若中间路径为非 dict（如 `llm.provider` 是字符串而非 dict），会静默返回 default。

**Suggested Fix**:
添加更详细的错误提示：
```python
def get(self, key: str, default=None):
    keys = key.split('.')
    value = self.config
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
            if value is None:
                return default
        else:
            logger.debug(f"Config path '{key}' has non-dict node at '{k}', returning default")
            return default
    return value
```

---

### [OPT-3] Controller._check_sensitive 可缓存结果
**Location**: `core/controller.py:27-30`
**Description**: 每次操作都调用 `is_operation_sensitive()`，如果操作类型固定可缓存结果。

**Suggested Fix**:
```python
from functools import lru_cache

@lru_cache(maxsize=32)  # 缓存常见操作类型的判断结果
def _check_sensitive(self, op_type: str, details: str = "") -> bool:
    if self.safe_guard.is_operation_sensitive(op_type):
        return self.safe_guard.request_confirmation(op_type, details)
    return True
```

---

### [OPT-4] PatternMiner.mine_patterns 可添加进度日志
**Location**: `learning/pattern_miner.py:14-25`
**Description**: 长动作序列挖掘可能耗时较长，添加进度提示改善用户体验。

**Suggested Fix**:
```python
def mine_patterns(self, actions: List[object]) -> List[Tuple[List[str], int]]:
    seq = [self._action_to_str(a) for a in actions]
    patterns = []
    total_lengths = self.max_length - self.min_length + 1
    for idx, length in enumerate(range(self.min_length, self.max_length + 1), 1):
        logger.info(f"Pattern mining progress: {idx}/{total_lengths} (length={length})")
        counter = Counter()
        for i in range(len(seq) - length + 1):
            pattern = tuple(seq[i:i + length])
            counter[pattern] += 1
        for pattern, count in counter.items():
            if count >= self.min_support:
                patterns.append((list(pattern), count))
    logger.info(f"Pattern mining completed: {len(patterns)} patterns found")
    return patterns
```

---

### [OPT-5] OpenAppSkill 可增加应用存在性检查
**Location**: `skills/native/open_app.py:98-115`
**Description**: 当前直接启动应用，失败时才报错。可预先检查应用是否存在（通过 shutil.which）。

**Suggested Fix**:
```python
import shutil

def execute(self, controller, **kwargs):
    app_name = kwargs["app_name"]
    # ... (安全校验保持不变)

    resolved = _resolve_app_name(app_name)
    system = platform.system()

    # 可选：检查可执行文件是否存在（Windows 下）
    if system == 'Windows':
        # 使用 where 命令查找
        try:
            result = subprocess.run(
                ['where', resolved],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                logger.warning(f"App '{resolved}' may not be in PATH")
        except Exception:
            pass  # 静默失败，不影响执行

    try:
        # ... (原有执行逻辑)
```

---

### [OPT-6] RLFineTuner 可添加训练进度回调
**Location**: `rl/trainer.py:50-126`
**Description**: 当前训练是阻塞的，长时间训练无法中断或查看进度。

**Suggested Fix**:
```python
from typing import Optional, Callable

class RLFineTuner:
    def __init__(self, base_model, tokenizer, skill_list, output_dir: str = None,
                 progress_callback: Optional[Callable[[float], None]] = None):
        # ... (原有代码)
        self.progress_callback = progress_callback

    def train(self, dataset, epochs=3):
        # ...
        class ProgressTrainer(Trainer):
            def __init__(self, *args, progress_callback, **kwargs):
                super().__init__(*args, **kwargs)
                self.progress_callback = progress_callback

            def log(self, logs: Dict[str, float]) -> None:
                super().log(logs)
                if self.progress_callback and "loss" in logs:
                    # 计算进度（简化：基于 epoch）
                    progress = logs.get("epoch", 0) / self.args.num_train_epochs
                    self.progress_callback(progress)

        trainer = ProgressTrainer(
            model=self.lora_model,
            args=training_args,
            train_dataset=train_dataset,
            progress_callback=self.progress_callback,
        )
        # ...
```

---

### [OPT-7] MainWindow 可添加退出清理
**Location**: `gui/main_window.py:188-189`
**Description**: 主窗口关闭时未清理资源（如线程、模型资源）。

**Suggested Fix**:
```python
def run(self):
    # 注册退出清理
    def on_closing():
        # 清理 daemon 线程（会自动结束）
        logger.info("GUI shutting down, cleaning resources...")
        # 可选：释放模型资源（需共享 ModelManager 引用）
        self.root.destroy()

    self.root.protocol("WM_DELETE_WINDOW", on_closing)
    self.root.mainloop()
```

---

## 总结

### 安全风险修复优先级

| 优先级 | ID | 问题 | 预计工作量 |
|--------|-----|------|-----------|
| P0 | SEC-1 | MCP 请求体大小限制 | 10 分钟 |
| P0 | SEC-6 | API 执行锁超时 | 15 分钟 |
| P1 | SEC-2 | Recognizer 路径遍历 | 10 分钟 |
| P1 | SEC-3 | RLFineTuner 原子写入 | 15 分钟 |
| P2 | SEC-5 | OllamaModel 健康检查验证 | 5 分钟 |
| P3 | SEC-4 | evolution.py UUID 冲突 | 5 分钟 |

### 代码优化优先级

- 高价值：OPT-6（训练进度回调）、OPT-4（挖掘进度日志）
- 低价值：其他优化可根据实际需求选择实施

---

## 测试建议

修复安全风险后，建议添加以下测试：

1. **DoS 攻击测试**：发送超大请求验证 MCP 服务器拒绝
2. **路径遍历测试**：尝试传入 `../../../etc/passwd` 验证被拦截
3. **超时测试**：发送超长执行命令验证 API 正确返回 408
4. **健康检查测试**：模拟 Ollama 返回非 JSON 验证判为不可用

---

**报告生成时间**: 2026-04-01 13:30
**审查文件数**: 43 个 Python 源文件
**审查代码行数**: 约 4000 行
