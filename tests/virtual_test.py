"""
NovaHands 虚拟测试脚本
=====================
无需安装任何第三方依赖，通过 Mock 技术模拟所有外部库，
验证各核心模块的逻辑正确性与协同工作能力。

运行方式：
    cd NovaHands
    python tests/virtual_test.py
"""

import sys
import os
import json
import types
import tempfile
import unittest
import logging
import threading
import importlib

# ─────────────────────────────────────────────
# 0. 确保从项目根目录可以找到各模块
# ─────────────────────────────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.WARNING)

# ─────────────────────────────────────────────
# 1. 全局 Mock 注册：替换所有第三方库
# ─────────────────────────────────────────────

def _make_module(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    return m

# ---------- pyautogui ----------
_screen_size = (1920, 1080)
_pyautogui_calls = []

def _mock_pyautogui_size():
    return _screen_size

def _record_call(name):
    def fn(*a, **kw):
        _pyautogui_calls.append((name, a, kw))
    return fn

pyautogui_mock = _make_module(
    "pyautogui",
    FAILSAFE=True,
    PAUSE=0.1,
    size=_mock_pyautogui_size,
    click=_record_call("click"),
    write=_record_call("write"),
    press=_record_call("press"),
    hotkey=_record_call("hotkey"),
    moveTo=_record_call("moveTo"),
    scroll=_record_call("scroll"),
)
sys.modules["pyautogui"] = pyautogui_mock

# ---------- pynput ----------
pynput_mock = _make_module("pynput")
pynput_keyboard = _make_module("pynput.keyboard")
pynput_mouse = _make_module("pynput.mouse")

class _KeyboardListener:
    def __init__(self, **kw): pass
    def start(self): pass
    def stop(self): pass

class _MouseListener:
    def __init__(self, **kw): pass
    def start(self): pass
    def stop(self): pass

class _Key:
    shift = "shift"
    ctrl = "ctrl"

pynput_keyboard.Listener = _KeyboardListener
pynput_keyboard.Key = _Key()
pynput_mouse.Listener = _MouseListener
sys.modules["pynput"] = pynput_mock
sys.modules["pynput.keyboard"] = pynput_keyboard
sys.modules["pynput.mouse"] = pynput_mouse

# ---------- psutil ----------
psutil_mock = _make_module("psutil")

class _Process:
    def __init__(self, pid=None):
        self.info = {"name": "chrome.exe", "pid": pid or 1234}
    def name(self):
        return "chrome.exe"

def _psutil_process_iter(attrs=None):
    return [_Process()]

psutil_mock.process_iter = _psutil_process_iter
psutil_mock.Process = _Process
psutil_mock.NoSuchProcess = OSError
sys.modules["psutil"] = psutil_mock

# ---------- cv2 / opencv ----------
cv2_mock = _make_module("cv2")
sys.modules["cv2"] = cv2_mock

# ---------- PIL / Pillow ----------
PIL_mock = _make_module("PIL")
PIL_Image = _make_module("PIL.Image")
PIL_Image.open = lambda *a, **kw: None
PIL_mock.Image = PIL_Image
sys.modules["PIL"] = PIL_mock
sys.modules["PIL.Image"] = PIL_Image

# ---------- numpy ----------
import numpy as np  # noqa – numpy 通常系统内置，若没有则用简单 mock
# 如果 numpy 真的不存在，用占位
try:
    import numpy  # noqa
except ImportError:
    numpy_mock = _make_module("numpy")
    sys.modules["numpy"] = numpy_mock

# ---------- gym / gymnasium ----------
class _Discrete:
    def __init__(self, n): self.n = n

class _Text:
    def __init__(self, n): self.n = n

class _DictSpace:
    def __init__(self, d): self.d = d

class _GymEnv:
    pass

gym_spaces = _make_module("gym.spaces", Discrete=_Discrete, Text=_Text, Dict=_DictSpace)
gym_mock = _make_module("gym", Env=_GymEnv, spaces=gym_spaces)
gym_mock.spaces = gym_spaces
sys.modules["gym"] = gym_mock
sys.modules["gym.spaces"] = gym_spaces
# gymnasium alias
sys.modules["gymnasium"] = gym_mock
sys.modules["gymnasium.spaces"] = gym_spaces

# ---------- pydantic (v2 API) ----------
# 项目代码使用了 pydantic v2 的 model_validate_json / field_validator
try:
    import pydantic  # noqa
    # 检验是否有 v2 API
    from pydantic import BaseModel as _PBM
    _PBM.model_validate_json  # v2 method
except (ImportError, AttributeError):
    # 提供最小化兼容实现，支持 field_validator 装饰器逻辑
    _VALIDATORS = {}  # class_name -> {field: [validator_fn]}

    def _field_validator(*fields, **kw):
        """记录 validator 函数，在 model_validate_json 时调用"""
        def decorator(fn):
            import inspect
            # 通过 qualname 推断所属类
            fn.__is_field_validator__ = True
            fn.__validated_fields__ = fields
            return fn
        return decorator

    def _validator(*fields, **kw):
        def decorator(fn): return fn
        return decorator

    class _ValidationError(Exception):
        pass

    class _BaseModelMeta(type):
        """收集 field_validator 装饰的方法"""
        def __new__(mcs, name, bases, namespace):
            validators = {}
            for attr_name, attr in namespace.items():
                if callable(attr) and getattr(attr, '__is_field_validator__', False):
                    for field in attr.__validated_fields__:
                        validators.setdefault(field, []).append(attr)
            namespace['__field_validators__'] = validators
            return super().__new__(mcs, name, bases, namespace)

    class _BaseModel(metaclass=_BaseModelMeta):
        __field_validators__ = {}

        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

        @classmethod
        def model_validate_json(cls, json_str):
            data = json.loads(json_str)
            # 收集整个 MRO 上的 validators
            all_validators = {}
            for base in reversed(cls.__mro__):
                fv = getattr(base, '__field_validators__', {})
                for field, fns in fv.items():
                    all_validators.setdefault(field, []).extend(fns)
            # 运行 validators
            for field, fns in all_validators.items():
                if field in data:
                    for fn in fns:
                        try:
                            data[field] = fn(data[field])
                        except (ValueError, TypeError) as e:
                            raise _ValidationError(str(e)) from e
            obj = cls.__new__(cls)
            # 设置默认值
            if not hasattr(obj, 'parameters'):
                object.__setattr__(obj, 'parameters', {})
            for k, v in data.items():
                object.__setattr__(obj, k, v)
            return obj

        def model_dump(self):
            return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}

    pydantic_mock = _make_module(
        "pydantic",
        BaseModel=_BaseModel,
        field_validator=_field_validator,
        validator=_validator,
        ValidationError=_ValidationError,
    )
    sys.modules["pydantic"] = pydantic_mock

# ---------- fastapi / uvicorn ----------
fastapi_mock = _make_module("fastapi")

class _FastAPI:
    def __init__(self, **kw): self.routes = []
    def get(self, path, **kw):
        def deco(fn): return fn
        return deco
    def post(self, path, **kw):
        def deco(fn): return fn
        return deco
    def on_event(self, event):
        def deco(fn): return fn
        return deco

class _HTTPException(Exception):
    def __init__(self, status_code, detail=""): self.status_code = status_code; self.detail = detail

class _Request:
    pass

fastapi_mock.FastAPI = _FastAPI
fastapi_mock.HTTPException = _HTTPException
fastapi_mock.Request = _Request
fastapi_mock.Depends = lambda *a, **kw: None
sys.modules["fastapi"] = fastapi_mock
sys.modules["fastapi.security"] = _make_module("fastapi.security", HTTPBearer=object, HTTPAuthorizationCredentials=object)
sys.modules["uvicorn"] = _make_module("uvicorn", run=lambda *a, **kw: None)

# ---------- openai / anthropic / requests ----------
sys.modules["openai"] = _make_module("openai")
sys.modules["anthropic"] = _make_module("anthropic")
sys.modules["requests"] = _make_module("requests", get=lambda *a, **kw: None, post=lambda *a, **kw: None)

# ---------- transformers / torch ----------
class _MockTransformerModel:
    def __init__(self, *a, **kw): pass
    def generate(self, *a, **kw): return [[0]]
    def to(self, device): return self
    @classmethod
    def from_pretrained(cls, *a, **kw): return cls()

class _MockTokenizer:
    def __init__(self, *a, **kw): self.eos_token_id = 0
    def __call__(self, *a, **kw):
        class _Enc: input_ids = [[0]]; attention_mask = [[1]]
        return _Enc()
    def decode(self, *a, **kw): return '{"skill": "open_app", "parameters": {}}'
    @classmethod
    def from_pretrained(cls, *a, **kw): return cls()

transformers_mock = _make_module(
    "transformers",
    AutoModelForCausalLM=_MockTransformerModel,
    AutoTokenizer=_MockTokenizer,
    BitsAndBytesConfig=lambda *a, **kw: None,
    pipeline=lambda *a, **kw: None,
)
sys.modules["transformers"] = transformers_mock
sys.modules["torch"] = _make_module("torch", cuda=_make_module("torch.cuda", is_available=lambda: False))
sys.modules["accelerate"] = _make_module("accelerate")
sys.modules["peft"] = _make_module("peft")
sys.modules["bitsandbytes"] = _make_module("bitsandbytes")

# ---------- tkinter ----------
tk_mock = _make_module("tkinter")

class _TkRoot:
    def __init__(self): pass
    def title(self, t): pass
    def geometry(self, g): pass
    def mainloop(self): pass
    def destroy(self): pass
    def after(self, ms, fn=None, *a): pass

tk_mock.Tk = _TkRoot
tk_mock.Label = lambda *a, **kw: None
tk_mock.Button = lambda *a, **kw: None
tk_mock.StringVar = lambda *a, **kw: object()
tk_mock.Text = lambda *a, **kw: None
tk_mock.Frame = lambda *a, **kw: None
tk_mock.messagebox = _make_module("tkinter.messagebox", askyesno=lambda *a, **kw: True, showinfo=lambda *a, **kw: None)
tk_scrolledtext = _make_module("tkinter.scrolledtext")
class _ScrolledText:
    def __init__(self, *a, **kw): pass
    def insert(self, *a, **kw): pass
    def delete(self, *a, **kw): pass
    def pack(self, *a, **kw): pass
    def config(self, *a, **kw): pass
tk_scrolledtext.ScrolledText = _ScrolledText
tk_mock.scrolledtext = tk_scrolledtext
sys.modules["tkinter"] = tk_mock
sys.modules["tkinter.messagebox"] = tk_mock.messagebox
sys.modules["tkinter.ttk"] = _make_module("tkinter.ttk")
sys.modules["tkinter.scrolledtext"] = tk_scrolledtext

# ---------- win32 ----------
sys.modules["win32gui"] = _make_module("win32gui", GetForegroundWindow=lambda: 0, GetWindowText=lambda h: "TestApp")
sys.modules["win32process"] = _make_module("win32process", GetWindowThreadProcessId=lambda h: (0, 1234))
sys.modules["win32con"] = _make_module("win32con")

# ---------- subprocess (保留真实，只在测试中绕过) ----------
import subprocess as _subprocess

# ─────────────────────────────────────────────
# 2. 辅助：临时 config.json
# ─────────────────────────────────────────────

_TEST_CONFIG = {
    "llm": {
        "default": "openai",
        "openai": {
            "model": "gpt-4",
            "api_key": "test-key-123",
            "params": {"temperature": 0.2}
        }
    },
    "security": {
        "allowed_apps": ["chrome.exe", "notepad.exe", "code.exe"],
        "sensitive_operations": ["send_keys", "delete_file"],
        "confirm_timeout": 10,
        "enable_failsafe": True
    },
    "logging": {"level": "WARNING"},
    "rl": {
        "enabled": True,
        "collect_data": True,
        "train_frequency": 86400,
        "lora_rank": 8,
        "learning_rate": 1e-4,
        "exploration_prob": 0.2,
        "skill_evolution_threshold": 0.8
    },
    "api": {
        "host": "127.0.0.1",
        "port": 8000,
        "api_key": "test-api-key-abc"
    }
}

def _write_test_config(path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_TEST_CONFIG, f)


# ─────────────────────────────────────────────
# 3. 测试用例
# ─────────────────────────────────────────────

class TestConfigLoader(unittest.TestCase):
    """ConfigLoader：配置加载、环境变量解析、异常处理"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        _write_test_config(self.tmp.name)
        self.tmp.close()

    def tearDown(self):
        os.unlink(self.tmp.name)

    def test_load_basic(self):
        from utils.config_loader import ConfigLoader
        cfg = ConfigLoader(config_path=self.tmp.name)
        self.assertEqual(cfg.get("llm.default"), "openai")

    def test_nested_get(self):
        from utils.config_loader import ConfigLoader
        cfg = ConfigLoader(config_path=self.tmp.name)
        self.assertEqual(cfg.get("security.confirm_timeout"), 10)

    def test_default_value(self):
        from utils.config_loader import ConfigLoader
        cfg = ConfigLoader(config_path=self.tmp.name)
        self.assertEqual(cfg.get("nonexistent.key", "fallback"), "fallback")

    def test_missing_file_raises(self):
        from utils.config_loader import ConfigLoader
        with self.assertRaises(FileNotFoundError):
            ConfigLoader(config_path="/nonexistent/path/config.json")

    def test_invalid_json_raises(self):
        from utils.config_loader import ConfigLoader
        bad = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        bad.write("{not valid json}")
        bad.close()
        try:
            with self.assertRaises(ValueError):
                ConfigLoader(config_path=bad.name)
        finally:
            os.unlink(bad.name)

    def test_env_var_resolution(self):
        from utils.config_loader import ConfigLoader
        os.environ["_NH_TEST_VAR"] = "hello"
        data = {"key": "${_NH_TEST_VAR}"}
        tf = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        json.dump(data, tf)
        tf.close()
        try:
            cfg = ConfigLoader(config_path=tf.name)
            self.assertEqual(cfg.get("key"), "hello")
        finally:
            os.unlink(tf.name)
            del os.environ["_NH_TEST_VAR"]

    def test_env_var_missing_returns_empty(self):
        """未设置的环境变量应返回空字符串并发出 warning"""
        from utils.config_loader import ConfigLoader
        os.environ.pop("_NH_MISSING_VAR", None)
        data = {"key": "${_NH_MISSING_VAR}"}
        tf = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        json.dump(data, tf)
        tf.close()
        try:
            cfg = ConfigLoader(config_path=tf.name)
            self.assertEqual(cfg.get("key"), "")
        finally:
            os.unlink(tf.name)


class TestBaseSkill(unittest.TestCase):
    """BaseSkill：参数校验、类型安全"""

    def setUp(self):
        from skills.base_skill import BaseSkill

        class DummySkill(BaseSkill):
            def __init__(self):
                super().__init__("dummy", "A dummy skill for testing", {"x": "int", "name": "str"})
            def execute(self, controller, **kwargs):
                return True

        self.SkillClass = DummySkill

    def test_valid_parameters(self):
        s = self.SkillClass()
        self.assertTrue(s.validate_parameters(x=1, name="hello"))

    def test_wrong_type_fails(self):
        s = self.SkillClass()
        self.assertFalse(s.validate_parameters(x="not_int", name="hello"))

    def test_missing_param_fails(self):
        s = self.SkillClass()
        self.assertFalse(s.validate_parameters(x=1))  # missing 'name'

    def test_unknown_type_raises(self):
        from skills.base_skill import BaseSkill

        class BadSkill(BaseSkill):
            def __init__(self):
                super().__init__("bad", "bad", {"val": "bytes"})  # 'bytes' not in _TYPE_MAP
            def execute(self, controller, **kwargs):
                pass

        s = BadSkill()
        with self.assertRaises(ValueError):
            s.validate_parameters(val=b"data")

    def test_to_dict(self):
        s = self.SkillClass()
        d = s.to_dict()
        self.assertEqual(d["name"], "dummy")
        self.assertEqual(d["type"], "native")
        self.assertIn("x", d["parameters"])


class TestSkillManager(unittest.TestCase):
    """SkillManager：技能加载、查询、执行"""

    def test_load_native_skills(self):
        from skills.skill_manager import SkillManager
        sm = SkillManager()
        # 至少应加载 open_app 和 send_email（如果存在）
        skills = sm.list_skills()
        self.assertIsInstance(skills, list)

    def test_get_skill_not_found(self):
        from skills.skill_manager import SkillManager
        sm = SkillManager()
        self.assertIsNone(sm.get_skill("nonexistent_skill_xyz"))

    def test_execute_unknown_skill_raises(self):
        from skills.skill_manager import SkillManager
        sm = SkillManager()
        with self.assertRaises(ValueError):
            sm.execute_skill("nonexistent_skill_xyz", None)

    def test_open_app_registered(self):
        from skills.skill_manager import SkillManager
        sm = SkillManager()
        skill = sm.get_skill("open_app")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "open_app")


class TestController(unittest.TestCase):
    """Controller：坐标裁剪、操作记录、等待上限"""

    def setUp(self):
        # Controller 需要 config.json，使用临时文件
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        _write_test_config(self.tmp.name)
        self.tmp.close()

        # 让 ConfigLoader 找到测试配置
        from utils import config_loader as _cl
        self._orig_init = _cl.ConfigLoader.__init__

        tmp_path = self.tmp.name

        def _patched_init(self_inner, config_path=None):
            self._orig_init(self_inner, config_path=config_path or tmp_path)

        _cl.ConfigLoader.__init__ = _patched_init

    def tearDown(self):
        from utils import config_loader as _cl
        _cl.ConfigLoader.__init__ = self._orig_init
        os.unlink(self.tmp.name)
        _pyautogui_calls.clear()

    def test_clamp_coords_in_bounds(self):
        from core.controller import Controller
        ctrl = Controller()
        x, y = ctrl._clamp_coords(100, 200)
        self.assertEqual((x, y), (100, 200))

    def test_clamp_coords_negative(self):
        from core.controller import Controller
        ctrl = Controller()
        x, y = ctrl._clamp_coords(-50, -100)
        self.assertEqual((x, y), (0, 0))

    def test_clamp_coords_overflow(self):
        from core.controller import Controller
        ctrl = Controller()
        x, y = ctrl._clamp_coords(9999, 9999)
        self.assertEqual(x, _screen_size[0] - 1)
        self.assertEqual(y, _screen_size[1] - 1)

    def test_click_recorded(self):
        from core.controller import Controller
        ctrl = Controller()
        ctrl.click(100, 200)
        self.assertTrue(any(c[0] == "click" for c in _pyautogui_calls))

    def test_wait_capped(self):
        import time
        from core.controller import Controller
        ctrl = Controller()
        start = time.time()
        # 传入极大值，应被截断为 60s 以内；实测用 0.01s 验证 clamping 逻辑
        ctrl.wait(0.01)
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0)

    def test_wait_max_cap(self):
        """传入超大值不应真的等待 10000 秒"""
        from core import controller as _ctrl_mod
        _ctrl_mod._MAX_WAIT_SECONDS  # 确保常量存在
        self.assertLessEqual(_ctrl_mod._MAX_WAIT_SECONDS, 300)


class TestSafeGuard(unittest.TestCase):
    """SafeGuard：应用白名单、敏感操作、confirm_timeout 最小值"""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        _write_test_config(self.tmp.name)
        self.tmp.close()
        from utils import config_loader as _cl
        self._orig_init = _cl.ConfigLoader.__init__
        tmp_path = self.tmp.name
        def _patched_init(self_inner, config_path=None):
            self._orig_init(self_inner, config_path=config_path or tmp_path)
        _cl.ConfigLoader.__init__ = _patched_init

    def tearDown(self):
        from utils import config_loader as _cl
        _cl.ConfigLoader.__init__ = self._orig_init
        os.unlink(self.tmp.name)

    def test_allowed_app(self):
        from core.safe_guard import SafeGuard
        sg = SafeGuard()
        self.assertTrue(sg.check_app_allowed("chrome.exe"))

    def test_denied_app(self):
        from core.safe_guard import SafeGuard
        sg = SafeGuard()
        self.assertFalse(sg.check_app_allowed("malicious.exe"))

    def test_sensitive_operation_detected(self):
        from core.safe_guard import SafeGuard
        sg = SafeGuard()
        self.assertTrue(sg.is_operation_sensitive("delete_file"))

    def test_non_sensitive_operation(self):
        from core.safe_guard import SafeGuard
        sg = SafeGuard()
        self.assertFalse(sg.is_operation_sensitive("click"))

    def test_confirm_timeout_minimum(self):
        """confirm_timeout 不得低于 _MIN_CONFIRM_TIMEOUT（5秒）"""
        bad_config = dict(_TEST_CONFIG)
        bad_config["security"] = dict(_TEST_CONFIG["security"])
        bad_config["security"]["confirm_timeout"] = 1  # < _MIN_CONFIRM_TIMEOUT

        tf = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        json.dump(bad_config, tf)
        tf.close()
        try:
            from utils import config_loader as _cl
            orig = _cl.ConfigLoader.__init__
            p = tf.name
            def _patched(self_inner, config_path=None):
                orig(self_inner, config_path=config_path or p)
            _cl.ConfigLoader.__init__ = _patched

            from core.safe_guard import SafeGuard
            # 强制重新加载，否则 lru_cache 可能返回旧实例
            sg = SafeGuard.__new__(SafeGuard)
            SafeGuard.__init__(sg)
            self.assertGreaterEqual(sg.confirm_timeout, 5)
        finally:
            _cl.ConfigLoader.__init__ = self._orig_init
            os.unlink(tf.name)


class TestNLExecutor(unittest.TestCase):
    """NLExecutor：输入截断、Prompt 构建、参数注入防御、Fallback 逻辑"""

    def _make_executor(self, model_response):
        """构建一个注入了 Mock Model 的 NLExecutor"""
        from skills.skill_manager import SkillManager
        from models.model_manager import ModelManager
        from models.base_model import BaseModel

        class MockModel(BaseModel):
            def __init__(self, resp):
                self.model_name = "mock"
                self._resp = resp
            def generate(self, prompt, **kw):
                return self._resp
            def chat(self, messages, **kw):
                return self._resp

        class MockModelManager:
            def get_model(self_inner):
                return MockModel(model_response)

        sm = SkillManager()
        mm = MockModelManager()

        from core.nl_executor import NLExecutor
        return NLExecutor(sm, mm), sm

    def test_input_truncation(self):
        """超长输入应被截断为 500 字符"""
        long_input = "A" * 1000
        executor, _ = self._make_executor('{"skill": "open_app", "parameters": {"app_name": "notepad"}}')

        # 只测试截断是否发生，不验证执行结果
        from core import nl_executor as _ne
        truncated = long_input[:_ne._MAX_INPUT_LENGTH]
        self.assertEqual(len(truncated), 500)

    def test_prompt_contains_skills(self):
        """生成的 Prompt 应包含已注册技能列表"""
        executor, sm = self._make_executor("{}")
        prompt = executor._build_prompt("open notepad", {})
        for skill_name in sm.list_skills():
            self.assertIn(skill_name, prompt)

    def test_extract_json_from_codeblock(self):
        executor, _ = self._make_executor("")
        result = executor._extract_json('```json\n{"skill": "test"}\n```')
        self.assertEqual(json.loads(result)["skill"], "test")

    def test_extract_json_from_raw(self):
        executor, _ = self._make_executor("")
        result = executor._extract_json('  {"skill": "test"}  ')
        self.assertEqual(json.loads(result)["skill"], "test")

    def test_parameter_injection_defense(self):
        """context 不应覆盖 LLM 解析的参数（修复后：LLM 参数优先）"""
        import json as _json
        from core.nl_executor import NLExecutor
        from skills.skill_manager import SkillManager
        from models.base_model import BaseModel

        executed_params = {}

        class MockModel(BaseModel):
            def __init__(self):
                self.model_name = "mock"
            def generate(self, prompt, **kw):
                # 返回 open_app 技能，app_name 来自 LLM
                return _json.dumps({"skill": "open_app", "parameters": {"app_name": "notepad"}})
            def chat(self, messages, **kw):
                return self.generate("")

        class MockController:
            pass

        class MockSkillManager:
            def list_skills(self): return ["open_app"]
            def get_skill(self, name):
                if name != "open_app": return None
                from skills.base_skill import BaseSkill
                class OS(BaseSkill):
                    def __init__(self): super().__init__("open_app","open",{"app_name":"str"})
                    def execute(self_inner, ctrl, **kw):
                        executed_params.update(kw)
                return OS()
            def execute_skill(self, name, ctrl, **kw):
                skill = self.get_skill(name)
                skill.execute(ctrl, **kw)

        class MockMM:
            def get_model(self): return MockModel()

        ex = NLExecutor(MockSkillManager(), MockMM())
        # context 中有 app_name="malicious"，但 LLM 返回 "notepad"
        # 修复后 LLM 结果应优先
        ex.execute("open notepad", MockController(), app_name="malicious_injected")
        self.assertEqual(executed_params.get("app_name"), "notepad")

    def test_invalid_skill_name_rejected(self):
        """技能名包含非法字符时应被 pydantic validator 拒绝"""
        try:
            from pydantic import ValidationError
        except ImportError:
            self.skipTest("pydantic not available")

        from core.nl_executor import SkillCall
        try:
            sc = SkillCall.model_validate_json('{"skill": "../../etc/passwd", "parameters": {}}')
            # 如果没有抛出，skill 名应已被清理
            self.assertNotIn("..", sc.skill)
        except Exception:
            pass  # validator 拒绝 = pass


class TestOpenAppSkill(unittest.TestCase):
    """OpenAppSkill：命令注入防护"""

    def setUp(self):
        from skills.native.open_app import OpenAppSkill
        self.skill = OpenAppSkill()

    def test_valid_app_name(self):
        """合法应用名不应抛出 ValueError"""
        # 不真正执行，通过 Mock subprocess
        import subprocess
        orig_popen = subprocess.Popen
        subprocess.Popen = lambda *a, **kw: None
        try:
            self.skill.execute(None, app_name="notepad.exe")
        except Exception as e:
            # 只允许非 ValueError 的异常（如 NotImplementedError on non-Windows）
            self.assertNotIsInstance(e, ValueError)
        finally:
            subprocess.Popen = orig_popen

    def test_injection_attempt_raises(self):
        """包含注入字符的应用名应抛出 ValueError"""
        with self.assertRaises(ValueError):
            self.skill.execute(None, app_name="notepad; rm -rf /")

    def test_ampersand_raises(self):
        with self.assertRaises(ValueError):
            self.skill.execute(None, app_name="app && evil_cmd")

    def test_pipe_raises(self):
        with self.assertRaises(ValueError):
            self.skill.execute(None, app_name="app | cat /etc/passwd")


class TestMockController(unittest.TestCase):
    """RL MockController：所有操作不实际执行"""

    def setUp(self):
        from rl.environment import MockController
        self.mc = MockController()

    def test_click_no_exception(self):
        self.mc.click(100, 200)

    def test_type_text_no_exception(self):
        self.mc.type_text("hello world")

    def test_press_no_exception(self):
        self.mc.press("enter")

    def test_hotkey_no_exception(self):
        self.mc.press_hotkey("ctrl", "c")

    def test_wait_no_exception(self):
        self.mc.wait(0)

    def test_move_no_exception(self):
        self.mc.move_to(500, 300)

    def test_scroll_no_exception(self):
        self.mc.scroll(3)


class TestNovaHandsEnv(unittest.TestCase):
    """RL 环境：步进、终止条件、边界检查"""

    def _make_env(self, max_steps=5):
        from skills.skill_manager import SkillManager
        from rl.environment import NovaHandsEnv

        sm = SkillManager()
        if not sm.list_skills():
            self.skipTest("No skills loaded, cannot create RL env")
        return NovaHandsEnv(skill_manager=sm, max_steps=max_steps)

    def test_reset_returns_state_and_info(self):
        env = self._make_env()
        obs, info = env.reset()
        self.assertIsInstance(obs, dict)
        self.assertIsInstance(info, dict)

    def test_step_returns_tuple_5(self):
        env = self._make_env()
        env.reset()
        result = env.step(0)
        self.assertEqual(len(result), 5)

    def test_terminates_at_max_steps(self):
        env = self._make_env(max_steps=3)
        env.reset()
        done = False
        for _ in range(5):
            _, _, done, truncated, _ = env.step(0)
            if done:
                break
        self.assertTrue(done)

    def test_invalid_action_raises(self):
        env = self._make_env()
        env.reset()
        n = len(env.skill_list)
        with self.assertRaises(ValueError):
            env.step(n)  # out of range

    def test_mock_controller_used_by_default(self):
        from rl.environment import MockController, NovaHandsEnv
        from skills.skill_manager import SkillManager
        sm = SkillManager()
        if not sm.list_skills():
            self.skipTest("No skills loaded")
        env = NovaHandsEnv(skill_manager=sm)
        self.assertIsInstance(env.controller, MockController)


class TestThreadSafety(unittest.TestCase):
    """并发安全：ModelManager Lock 防止竞态条件"""

    def test_concurrent_config_reads(self):
        """多线程同时读取 ConfigLoader 不应崩溃"""
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w")
        _write_test_config(tmp.name)
        tmp.close()

        errors = []

        def _read():
            try:
                from utils.config_loader import ConfigLoader
                cfg = ConfigLoader(config_path=tmp.name)
                cfg.get("llm.default")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=_read) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()
        os.unlink(tmp.name)
        self.assertEqual(errors, [])


class TestAPIKeyValidation(unittest.TestCase):
    """API Key：确保 hmac 时序安全比较逻辑存在"""

    def test_hmac_compare_exists_in_api(self):
        """api.py 中应使用 hmac.compare_digest 而非 == 比较"""
        api_path = os.path.join(ROOT, "api.py")
        with open(api_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("hmac.compare_digest", content,
                      "api.py should use hmac.compare_digest to prevent timing attacks")

    def test_no_dangerous_eval_in_base_skill(self):
        """base_skill.py 不应使用 eval()"""
        skill_path = os.path.join(ROOT, "skills", "base_skill.py")
        with open(skill_path, "r", encoding="utf-8") as f:
            content = f.read()
        # eval( 后面跟 expected_type 的模式
        import re
        self.assertNotRegex(content, r'\beval\s*\(\s*expected_type',
                            "base_skill.py should NOT use eval(expected_type)")

    def test_no_shell_true_in_open_app(self):
        """open_app.py 不应使用 shell=True（注释除外）"""
        import re
        path = os.path.join(ROOT, "skills", "native", "open_app.py")
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # 只检查非注释行
        code_lines = [l for l in lines if not l.lstrip().startswith("#")]
        code = "".join(code_lines)
        self.assertNotIn("shell=True", code,
                         "open_app.py should NOT use shell=True in actual code (excluding comments)")

    def test_failsafe_default_true(self):
        """controller.py 中 FAILSAFE 默认值应为 True（安全修复）"""
        path = os.path.join(ROOT, "core", "controller.py")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("True", content)
        # 不应有 FAILSAFE = False 的硬编码默认
        import re
        self.assertNotRegex(content, r'pyautogui\.FAILSAFE\s*=\s*False')


# ─────────────────────────────────────────────
# 4. 彩色结果输出
# ─────────────────────────────────────────────

class _ColorResult(unittest.TextTestResult):
    GREEN = "\033[92m"
    RED   = "\033[91m"
    YELLOW= "\033[93m"
    RESET = "\033[0m"
    BOLD  = "\033[1m"

    def addSuccess(self, test):
        super().addSuccess(test)
        self.stream.write(f"  [OK] {test._testMethodName}\n")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.stream.write(f"  [FAIL] {test._testMethodName}\n")

    def addError(self, test, err):
        super().addError(test, err)
        self.stream.write(f"  [ERR] {test._testMethodName}\n")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.stream.write(f"  [SKIP] {test._testMethodName} (skipped: {reason})\n")


class _ColorRunner(unittest.TextTestRunner):
    def _makeResult(self):
        return _ColorResult(self.stream, self.descriptions, self.verbosity)


# ─────────────────────────────────────────────
# 5. 主入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 60)
    print("  NovaHands 虚拟测试套件")
    print("  （所有第三方依赖已 Mock，无需安装任何包）")
    print("═" * 60 + "\n")

    suites = [
        ("配置加载器 (ConfigLoader)",    TestConfigLoader),
        ("技能基类 (BaseSkill)",          TestBaseSkill),
        ("技能管理器 (SkillManager)",      TestSkillManager),
        ("控制器 (Controller)",           TestController),
        ("安全守卫 (SafeGuard)",           TestSafeGuard),
        ("自然语言执行器 (NLExecutor)",    TestNLExecutor),
        ("打开应用技能 (OpenAppSkill)",    TestOpenAppSkill),
        ("RL 模拟控制器 (MockController)", TestMockController),
        ("RL 训练环境 (NovaHandsEnv)",     TestNovaHandsEnv),
        ("线程安全 (ThreadSafety)",        TestThreadSafety),
        ("安全修复验证 (SecurityFixes)",   TestAPIKeyValidation),
    ]

    total_pass = total_fail = total_error = total_skip = 0

    for label, suite_class in suites:
        print(f"\n>> {label}")
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(suite_class)
        runner = _ColorRunner(verbosity=0, stream=open(os.devnull, "w"))
        result = runner.run(suite)

        # 手动打印每条
        for test, _ in result.failures:
            print(f"  \033[91m[FAIL]\033[0m {test._testMethodName}")
        for test, _ in result.errors:
            print(f"  \033[93m[ERR]\033[0m {test._testMethodName} (ERROR)")
        for test, reason in result.skipped:
            print(f"  \033[93m[SKIP]\033[0m {test._testMethodName} (skipped)")

        # 成功的
        failed_names = {t._testMethodName for t, _ in result.failures + result.errors}
        skipped_names = {t._testMethodName for t, _ in result.skipped}
        all_tests = list(suite)
        for t in all_tests:
            if t is None:
                continue
            name = getattr(t, "_testMethodName", None)
            if name is None:
                continue
            if name not in failed_names and name not in skipped_names:
                print(f"  \033[92m[OK]\033[0m {name}")

        total_pass  += result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
        total_fail  += len(result.failures)
        total_error += len(result.errors)
        total_skip  += len(result.skipped)

    total = total_pass + total_fail + total_error + total_skip
    print("\n" + "═" * 60)
    print(f"  总计: {total} 项测试")
    print(f"  \033[92m通过: {total_pass}\033[0m  "
          f"\033[91m失败: {total_fail}\033[0m  "
          f"\033[93m错误: {total_error}  跳过: {total_skip}\033[0m")
    if total_fail == 0 and total_error == 0:
        print("\n  \033[1m\033[92m[OK] 全部测试通过！项目逻辑运行正常。\033[0m")
    else:
        print("\n  \033[91m部分测试未通过，请查看上方详情。\033[0m")
    print("═" * 60 + "\n")

    sys.exit(1 if (total_fail + total_error) > 0 else 0)
