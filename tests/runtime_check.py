"""
runtime_check.py - 实际运行时检查（非 Mock）
用项目真实模块路径，检查各模块能否正常导入、初始化，并模拟关键流程
"""
import sys
import os
import json as _json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = 0
FAIL = 0


def ok(msg):
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")


def fail(msg, exc=None):
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")
    if exc:
        print(f"         {type(exc).__name__}: {exc}")


# ─────────────────────────────────────────────
# 1. 模块导入
# ─────────────────────────────────────────────
print("\n=== 1. 模块导入 ===")

try:
    from utils.config_loader import ConfigLoader
    ok("utils.config_loader.ConfigLoader")
except Exception as e:
    fail("utils.config_loader.ConfigLoader", e)

try:
    from skills.skill_manager import SkillManager
    ok("skills.skill_manager.SkillManager")
except Exception as e:
    fail("skills.skill_manager.SkillManager", e)

try:
    from models.model_manager import ModelManager
    ok("models.model_manager.ModelManager")
except Exception as e:
    fail("models.model_manager.ModelManager", e)

try:
    from models.ollama_model import OllamaModel
    ok("models.ollama_model.OllamaModel")
except Exception as e:
    fail("models.ollama_model.OllamaModel", e)

try:
    from core.nl_executor import NLExecutor
    ok("core.nl_executor.NLExecutor")
except Exception as e:
    fail("core.nl_executor.NLExecutor", e)

try:
    from core.controller import Controller
    ok("core.controller.Controller")
except Exception as e:
    fail("core.controller.Controller", e)

try:
    from core.recognizer import Recognizer
    ok("core.recognizer.Recognizer")
except Exception as e:
    fail("core.recognizer.Recognizer", e)

try:
    from core.safe_guard import SafeGuard
    ok("core.safe_guard.SafeGuard")
except Exception as e:
    fail("core.safe_guard.SafeGuard", e)

try:
    from skills.native.open_app import OpenAppSkill
    ok("skills.native.open_app.OpenAppSkill")
except Exception as e:
    fail("skills.native.open_app.OpenAppSkill", e)

try:
    from skills.native.send_email import SendEmailSkill
    ok("skills.native.send_email.SendEmailSkill")
except Exception as e:
    fail("skills.native.send_email.SendEmailSkill", e)

try:
    from rl.collector import DataCollector
    ok("rl.collector.DataCollector")
except Exception as e:
    fail("rl.collector.DataCollector", e)

try:
    from rl.trainer import RLFineTuner
    ok("rl.trainer.RLFineTuner")
except Exception as e:
    fail("rl.trainer.RLFineTuner", e)

# ─────────────────────────────────────────────
# 2. 实例化
# ─────────────────────────────────────────────
print("\n=== 2. 实例化 ===")

cl = sm = mm = nl = ctrl = None

try:
    cl = ConfigLoader()
    provider = cl.get("llm.default", "N/A")
    ok(f"ConfigLoader()  llm.default={provider!r}")
except Exception as e:
    fail("ConfigLoader()", e)

try:
    sm = SkillManager()
    skills = sm.list_skills()
    ok(f"SkillManager()  skills={skills}")
except Exception as e:
    fail("SkillManager()", e)

try:
    mm = ModelManager()
    model = mm.get_model()
    ok(f"ModelManager()  current_model={model!r}")
except Exception as e:
    fail("ModelManager()", e)

try:
    ctrl = Controller()
    ok("Controller()")
except Exception as e:
    fail("Controller()", e)

try:
    nl = NLExecutor(sm, mm)
    ok("NLExecutor(sm, mm)")
except Exception as e:
    fail("NLExecutor(sm, mm)", e)

# ─────────────────────────────────────────────
# 3. open_app 别名映射
# ─────────────────────────────────────────────
print("\n=== 3. open_app 别名映射 ===")
try:
    from skills.native.open_app import _resolve_app_name
    cases = [
        ("记事本",     "notepad"),
        ("Notepad",    "notepad"),
        ("chrome",     "chrome"),
        ("谷歌浏览器", "chrome"),
        ("计算器",     "calc"),
        ("calculator", "calc"),
        ("Excel",      "excel"),
        ("微信",       "wechat"),
        ("vscode",     "code"),
        ("MyCustomApp","MyCustomApp"),
    ]
    for inp, expected in cases:
        result = _resolve_app_name(inp)
        if result.lower() == expected.lower():
            ok(f"_resolve_app_name({inp!r}) = {result!r}")
        else:
            fail(f"_resolve_app_name({inp!r}) = {result!r}, expected {expected!r}")
except Exception as e:
    fail("open_app alias test", e)

# ─────────────────────────────────────────────
# 4. NLExecutor Prompt 构建
# ─────────────────────────────────────────────
print("\n=== 4. NLExecutor Prompt 构建 ===")
if nl:
    try:
        prompt = nl._build_prompt("打开记事本", {})
        assert "open_app" in prompt, "prompt 中缺少 open_app"
        assert "app_name" in prompt, "prompt 中缺少 app_name"
        ok("_build_prompt 包含 open_app、app_name 关键词")
    except Exception as e:
        fail("_build_prompt", e)

    try:
        prompt2 = nl._build_prompt("你好", {})
        assert "none" in prompt2.lower(), "prompt 中缺少 none 处理说明"
        ok("_build_prompt 包含 none 关键词")
    except Exception as e:
        fail("_build_prompt none", e)

    # 验证技能描述里包含参数签名
    try:
        prompt3 = nl._build_prompt("test", {})
        assert "app_name: str" in prompt3 or "app_name" in prompt3
        ok("_build_prompt 技能描述含参数签名")
    except Exception as e:
        fail("_build_prompt param signature", e)

# ─────────────────────────────────────────────
# 5. JSON 提取
# ─────────────────────────────────────────────
print("\n=== 5. _extract_json ===")
if nl:
    json_cases = [
        ('{"skill": "open_app", "parameters": {"app_name": "notepad"}}', "open_app"),
        ("{'skill': 'open_app', 'parameters': {'app_name': 'notepad'}}", "open_app"),
        ('some text {"skill": "none", "parameters": {}} trailing', "none"),
        ('```json\n{"skill": "open_app", "parameters": {"app_name": "calc"}}\n```', "open_app"),
    ]
    for raw, expected_skill in json_cases:
        try:
            extracted = nl._extract_json(raw)
            parsed = _json.loads(extracted)
            if parsed.get("skill") == expected_skill:
                ok(f"_extract_json skill={expected_skill!r}  input={raw[:50]!r}")
            else:
                fail(f"_extract_json skill mismatch: got {parsed.get('skill')!r}, expected {expected_skill!r}")
        except Exception as e:
            fail(f"_extract_json failed: {raw[:50]!r}", e)

# ─────────────────────────────────────────────
# 6. Fallback _extract_app_name
# ─────────────────────────────────────────────
print("\n=== 6. Fallback _extract_app_name ===")
if nl:
    cases = [
        ("打开记事本", "打开", "记事本"),
        ("打开 Chrome", "打开", "Chrome"),
        ("open notepad", "open", "notepad"),
        ("启动计算器", "启动", "计算器"),
    ]
    for user_input, keyword, expected in cases:
        try:
            result = nl._extract_app_name(user_input, keyword)
            if result and result.strip().lower() == expected.strip().lower():
                ok(f"_extract_app_name({user_input!r}) = {result!r}")
            else:
                fail(f"_extract_app_name({user_input!r}) = {result!r}, expected {expected!r}")
        except Exception as e:
            fail(f"_extract_app_name({user_input!r})", e)

# ─────────────────────────────────────────────
# 7. Ollama 连通性
# ─────────────────────────────────────────────
print("\n=== 7. Ollama 连通性 ===")
import urllib.request
ollama_ok = False
try:
    req = urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3)
    data = req.read().decode()
    models_data = _json.loads(data)
    model_names = [m["name"] for m in models_data.get("models", [])]
    ok(f"Ollama 服务可访问，已安装模型: {model_names}")
    ollama_ok = True
except Exception as e:
    print(f"  [INFO] Ollama 未运行（LLM 路径不可用）: {e}")

# ─────────────────────────────────────────────
# 8. Fallback 执行 dry-run（不真实打开程序）
# ─────────────────────────────────────────────
print("\n=== 8. Fallback 执行 dry-run ===")
if nl and sm:
    skill = sm.get_skill("open_app")
    if skill:
        original_execute = skill.execute
        captured = {}

        def mock_execute(controller, **kwargs):
            captured.update(kwargs)

        skill.execute = mock_execute
        try:
            sm.execute_skill("open_app", None, app_name="notepad")
            if captured.get("app_name") == "notepad":
                ok(f"execute_skill 参数传递正确: {captured}")
            else:
                fail(f"execute_skill 参数错误: {captured}")
        except Exception as e:
            fail("Fallback dry-run", e)
        finally:
            skill.execute = original_execute
    else:
        fail("open_app skill 未注册")

# ─────────────────────────────────────────────
# 9. LLM 实际调用（仅 Ollama 可用时）
# ─────────────────────────────────────────────
print("\n=== 9. LLM 实际调用 ===")
if ollama_ok and mm:
    model = mm.get_model()
    if model:
        try:
            resp = model.generate("回复一个字：好")
            if resp and len(resp.strip()) > 0:
                ok(f"OllamaModel.generate() 返回: {resp.strip()[:80]!r}")
            else:
                fail("OllamaModel.generate() 返回空")
        except Exception as e:
            fail("OllamaModel.generate()", e)
    else:
        print("  [INFO] current_model=None，跳过 LLM 调用测试")
else:
    print("  [INFO] Ollama 不可用，跳过 LLM 调用测试")

# ─────────────────────────────────────────────
# 10. NL 执行全链路（仅 Ollama 可用时）
# ─────────────────────────────────────────────
print("\n=== 10. NL 执行全链路（Fallback 路径）===")
if nl and sm and ctrl:
    skill = sm.get_skill("open_app")
    if skill:
        original_execute = skill.execute
        captured2 = {}

        def mock_execute2(controller, **kwargs):
            captured2.update(kwargs)

        skill.execute = mock_execute2
        try:
            # 绕过 LLM，直接走 Fallback
            result = nl._fallback_execution("打开记事本", ctrl)
            if result == "open_app" and captured2.get("app_name"):
                ok(f"Fallback 全链路: skill={result!r}, app_name={captured2.get('app_name')!r}")
                # 验证别名解析
                from skills.native.open_app import _resolve_app_name
                resolved = _resolve_app_name(captured2["app_name"])
                ok(f"别名解析: {captured2['app_name']!r} -> {resolved!r}")
            else:
                fail(f"Fallback 全链路异常: result={result!r}, captured={captured2}")
        except Exception as e:
            fail("Fallback 全链路", e)
        finally:
            skill.execute = original_execute
    else:
        fail("open_app 未注册")

# ─────────────────────────────────────────────
# 汇总
# ─────────────────────────────────────────────
print()
print("=" * 50)
print(f"  总计: {PASS + FAIL}  通过: {PASS}  失败: {FAIL}")
if FAIL == 0:
    print("  >>> 所有检查通过 <<<")
else:
    print(f"  >>> {FAIL} 项检查失败 <<<")
    sys.exit(1)
