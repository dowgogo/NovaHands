import json
import re
import time
import difflib
import logging
from pydantic import BaseModel, ValidationError, field_validator
from typing import Dict, Any, Optional
from skills.skill_manager import SkillManager
from models.model_manager import ModelManager
from core.executor_memory import ExecutorMemory, ExecutionRecord

# 关键词 → 技能名映射表（fallback 模式用）
_KEYWORD_MAP = {
    # 打开应用
    "打开": "open_app",
    "open": "open_app",
    "启动": "open_app",
    "运行": "open_app",
    "launch": "open_app",
    # 截图
    "截图": "screenshot",
    "截屏": "screenshot",
    "screenshot": "screenshot",
    # 搜索
    "搜索": "web_search",
    "search": "web_search",
    "查一下": "web_search",
    "查找": "web_search",
    # 关闭
    "关闭": "close_app",
    "close": "close_app",
    "退出": "close_app",
    "exit": "close_app",
    # 鼠标点击
    "点击": "mouse_click",
    "click": "mouse_click",
    "单击": "mouse_click",
    # 键盘输入
    "输入": "type_text",
    "type": "type_text",
    "键入": "type_text",
    # 滚动
    "滚动": "scroll",
    "scroll": "scroll",
}

logger = logging.getLogger('novahands')

# 用户输入最大长度限制，防止 Prompt Injection 超长输入
_MAX_INPUT_LENGTH = 500


class SkillCall(BaseModel):
    skill: str
    parameters: Dict[str, Any] = {}

    @field_validator('skill')
    @classmethod
    def skill_must_be_simple(cls, v: str) -> str:
        """技能名只允许字母、数字、下划线、连字符，或特殊值 'none'"""
        if v == "none":
            return v
        if not re.match(r'^[\w\-]+$', v):
            raise ValueError(f"Invalid skill name: '{v}'")
        return v.strip()


class NLExecutor:
    def __init__(self, skill_manager: SkillManager, model_manager: ModelManager,
                 memory: Optional[ExecutorMemory] = None):
        self.skill_manager = skill_manager
        self.model_manager = model_manager  # 保存 manager 引用，每次执行时动态取模型
        # 执行历史记忆：默认创建，也可从外部注入（便于测试）
        self.memory = memory if memory is not None else ExecutorMemory()
        # 最大 LLM 重试次数（错误自恢复，参考 AgentDebug 框架）
        self._max_retries = 2

    def execute(self, user_input: str, controller, **context) -> Optional[str]:
        """执行用户指令，返回实际执行的技能名；未匹配时返回 None。"""
        # 对用户输入做长度限制，防止 Prompt Injection 超长攻击
        user_input = user_input[:_MAX_INPUT_LENGTH]

        # 每次执行时动态获取当前模型（避免初始化顺序导致拿到 None）
        model = self.model_manager.get_model()

        # model=None（provider=none）时直接走 fallback，不尝试调用 LLM
        if model is None:
            logger.info("No LLM available, using fallback keyword matching")
            return self._fallback_execution(user_input, controller, **context)

        return self._execute_with_retry(user_input, controller, model, **context)

    def _execute_with_retry(self, user_input: str, controller, model,
                            **context) -> Optional[str]:
        """带自动重试的 LLM 执行（错误自恢复机制）。

        重试策略（参考 AgentDebug 框架）：
        - 第 1 次：正常执行
        - 第 2 次（若失败）：在 Prompt 中注入失败原因，引导 LLM 修正
        - 第 3 次（若仍失败）：降级到 fallback 关键词匹配
        """
        last_error: Optional[str] = None
        for attempt in range(self._max_retries + 1):
            prompt = self._build_prompt(user_input, context,
                                        retry_hint=last_error if attempt > 0 else None)
            response = None
            t_start = time.monotonic()
            try:
                response = model.generate(prompt, temperature=0.2)
                logger.info(f"[LLM RAW attempt={attempt}] {response!r}")
                json_str = self._extract_json(response)
                skill_call = SkillCall.model_validate_json(json_str)
                skill_name = skill_call.skill

                # skill=none 表示 LLM 认为无需执行任何技能（如问候、闲聊）
                if skill_name == "none":
                    logger.info("LLM determined no skill needed for this input")
                    return None

                # 技能名白名单校验：只允许已注册的技能
                if not self.skill_manager.get_skill(skill_name):
                    raise ValueError(f"Skill '{skill_name}' not found in registry")

                # 安全合并：以模型解析结果为主，context 仅补充不覆盖
                params = {**context, **skill_call.parameters}

                self.skill_manager.execute_skill(skill_name, controller, **params)
                duration = time.monotonic() - t_start
                logger.info(f"Executed skill: {skill_name} (attempt={attempt}, {duration:.2f}s)")

                # 记录成功执行到 memory
                self.memory.add(ExecutionRecord(
                    skill_name=skill_name,
                    parameters=skill_call.parameters,
                    success=True,
                    duration=duration,
                ))
                return skill_name

            except Exception as e:
                duration = time.monotonic() - t_start
                resp_preview = (response[:300] if response else "<no response>")
                error_str = str(e)
                logger.error(
                    f"Execution failed (attempt={attempt}): {error_str}\n"
                    f"Raw response: {resp_preview!r}"
                )
                # 记录失败到 memory
                self.memory.add(ExecutionRecord(
                    skill_name="unknown",
                    parameters={},
                    success=False,
                    error_msg=error_str[:200],
                    duration=duration,
                ))
                last_error = error_str
                # 若还有重试机会，继续；否则降级 fallback
                if attempt < self._max_retries:
                    logger.info(f"Retrying with error context (attempt {attempt + 1}/{self._max_retries})...")
                    continue

        # 所有重试耗尽，降级 fallback
        logger.warning("All LLM retries exhausted, falling back to keyword matching")
        return self._fallback_execution(user_input, controller, **context)

    def _extract_json(self, text: str) -> str:
        """从 LLM 输出中提取 JSON 字符串。

        处理小模型常见的不规范输出：
        1. ```json ... ``` 代码块
        2. ``` ... ``` 代码块
        3. 文本中内嵌的 {...} 花括号（最常见）
        4. 单引号替换为双引号（部分模型习惯）
        """
        # 优先处理代码块
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end == -1:
                raise ValueError("Truncated LLM response: opening ```json found but closing ``` missing")
            return text[start:end].strip()
        if "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end == -1:
                raise ValueError("Truncated LLM response: opening ``` found but closing ``` missing")
            candidate = text[start:end].strip()
            if candidate.startswith("{"):
                return candidate

        # 从文本中提取第一个完整的 {...} 块（处理模型在 JSON 前后附加说明文字的情况）
        # 使用状态机正确处理字符串内的 {} 字符，避免提前截断
        brace_start = text.find("{")
        if brace_start != -1:
            depth = 0
            in_string = False
            escape_next = False
            for i, ch in enumerate(text[brace_start:], start=brace_start):
                if escape_next:
                    escape_next = False
                    continue
                if ch == '' and in_string:
                    escape_next = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[brace_start:i + 1].strip()
                        # 兼容：部分小模型用单引号作为 JSON key/value 的边界引号
                        # 只替换作为 JSON 边界的单引号（key 或 value 开头/结尾），
                        # 不替换值内部的撇号（如 "it's"）
                        # 简单启发：如果不含双引号，则整体替换单引号为双引号
                        if '"' not in candidate and "'" in candidate:
                            candidate = candidate.replace("'", '"')
                        return candidate
            raise ValueError("Truncated JSON: opening { found but no matching }")

        return text.strip()

    def _fallback_execution(self, user_input: str, controller, **context) -> Optional[str]:
        """三层 Fallback：
        1. 精确名称匹配（用户直接输入技能名）
        2. 关键词映射（中英文关键词 → 技能名）
        3. 模糊匹配（difflib，相似度 >= 0.6）
        安全：不传入 context，防止参数注入
        """
        text = user_input.strip().lower()
        available = self.skill_manager.list_skills()

        # 层 1：精确匹配
        if self.skill_manager.get_skill(text):
            logger.info(f"Fallback: exact match → '{text}'")
            return self._run_fallback_skill(text, controller)

        # 层 2：关键词映射
        for keyword, skill_name in _KEYWORD_MAP.items():
            if keyword in text and self.skill_manager.get_skill(skill_name):
                logger.info(f"Fallback: keyword '{keyword}' → '{skill_name}'")
                # open_app 需要 app_name 参数，从用户输入中提取
                extra_params = {}
                if skill_name == "open_app":
                    app_name = self._extract_app_name(user_input, keyword)
                    if app_name:
                        extra_params["app_name"] = app_name
                return self._run_fallback_skill(skill_name, controller, **extra_params)

        # 层 3：模糊匹配（cutoff=0.6）
        close = difflib.get_close_matches(text, available, n=1, cutoff=0.6)
        if close:
            logger.info(f"Fallback: fuzzy match '{text}' → '{close[0]}'")
            return self._run_fallback_skill(close[0], controller)

        logger.warning(f"Fallback: no match for command (truncated): {user_input[:100]!r}")
        return None

    def _extract_app_name(self, user_input: str, trigger_keyword: str) -> Optional[str]:
        """从用户输入中提取应用名（去掉触发关键词后的剩余部分）。"""
        # 去掉触发关键词，取剩余部分作为应用名
        text = user_input.strip()
        # 大小写不敏感地去除关键词
        pattern = re.compile(re.escape(trigger_keyword), re.IGNORECASE)
        app_name = pattern.sub("", text).strip()
        # 去掉多余的标点
        app_name = app_name.strip("：:，,。.！!？? ")
        if app_name:
            logger.info(f"Fallback extracted app_name: '{app_name}'")
            return app_name
        return None

    def _run_fallback_skill(self, skill_name: str, controller, **extra_params) -> str:
        """执行 fallback 技能，可携带提取到的参数"""
        try:
            self.skill_manager.execute_skill(skill_name, controller, **extra_params)
            logger.info(f"Fallback execution succeeded: {skill_name}")
            return skill_name
        except Exception as e:
            logger.error(f"Fallback execution failed for '{skill_name}': {e}")
            return None

    def _build_prompt(self, user_input: str, context: dict,
                      retry_hint: Optional[str] = None) -> str:
        """构建 LLM Prompt，支持重试提示注入（错误自恢复）。

        若 retry_hint 非空，在 Prompt 中注入：
        1. 前次执行历史摘要
        2. 失败原因和修正建议
        这样 LLM 可在第 2 次尝试时自我纠错。
        """
        skill_list = self.skill_manager.list_skills()
        # 构建带参数签名的技能描述
        skill_descriptions_parts = []
        for name in skill_list:
            skill = self.skill_manager.get_skill(name)
            params_hint = ", ".join(
                f"{k}: {v}" for k, v in (skill.parameters or {}).items()
            )
            if params_hint:
                skill_descriptions_parts.append(
                    f"- {name}({params_hint}): {skill.description}"
                )
            else:
                skill_descriptions_parts.append(f"- {name}: {skill.description}")
        skill_descriptions = "\n".join(skill_descriptions_parts)

        # 对 user_input 做简单转义，降低 Prompt Injection 风险
        safe_input = user_input.replace("```", "'''")
        # Bug fix: context 可能为 None（调用方传入 None 时 json.dumps 会崩溃）
        safe_context = context if context is not None else {}

        base_prompt = f"""你是一个智能桌面助手，将用户的自然语言指令转换为 JSON 技能调用。

可用技能（括号内为必填参数）：
{skill_descriptions}
- none: 用于问候、闲聊、感谢、或不需要执行操作的输入

当前上下文（仅供参考）：
{json.dumps(safe_context, ensure_ascii=False)}

用户指令：{safe_input}

判断规则：
1. 打开/启动/运行某个应用 → open_app，app_name 填应用名称（英文，如 notepad、chrome、calc）
2. 发送邮件 → send_email，填写 recipient、subject、body
3. 问候语/闲聊/不需要操作 → none
4. 不确定 → none

示例：
用户说"打开记事本" → {{"skill": "open_app", "parameters": {{"app_name": "notepad"}}}}
用户说"open chrome" → {{"skill": "open_app", "parameters": {{"app_name": "chrome"}}}}
用户说"你好" → {{"skill": "none", "parameters": {{}}}}

只输出 JSON，不要包含任何解释文字："""

        # 若是重试请求，追加错误诊断上下文
        if retry_hint:
            history = self.memory.build_context_summary(max_lines=4)
            pattern_hint = self.memory.error_pattern_hint()
            error_context = f"""

【重试诊断】
前次尝试失败：{retry_hint[:150]}
执行历史摘要：
{history}"""
            if pattern_hint:
                error_context += f"\n\n{pattern_hint}"
            error_context += "\n请基于上述错误诊断，尝试选择不同的技能或修正参数。"
            return base_prompt + error_context
        return base_prompt
