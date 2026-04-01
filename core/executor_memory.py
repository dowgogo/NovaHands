"""executor_memory.py — 执行历史记忆模块

灵感来源：
  - Letta（MemGPT）三层记忆架构（Core / Recall / Archival）
  - AgentDebug 错误诊断框架（+26% 任务成功率）

本模块提供：
  1. ExecutionRecord — 单次执行记录（技能名、参数、结果、错误信息）
  2. ExecutorMemory   — 执行历史管理器
     - 短期记忆（最近 N 条，用于构建上下文 Prompt）
     - 错误摘要（最近失败记录，用于指导重试）
     - 持久化（JSON 文件，跨会话保留）
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("novahands")

# 短期记忆最大条数（内存中保留）
_SHORT_TERM_MAX = 20
# 持久化文件最大条数（写入磁盘的历史）
_PERSIST_MAX = 200


@dataclass
class ExecutionRecord:
    """单次技能执行记录。"""
    skill_name: str
    parameters: dict
    success: bool
    error_msg: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    # 执行耗时（秒），-1 表示未记录
    duration: float = -1.0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "ExecutionRecord":
        return ExecutionRecord(
            skill_name=d.get("skill_name", "unknown"),
            parameters=d.get("parameters", {}),
            success=d.get("success", False),
            error_msg=d.get("error_msg"),
            timestamp=d.get("timestamp", 0.0),
            duration=d.get("duration", -1.0),
        )


class ExecutorMemory:
    """执行历史记忆管理器。

    Usage::

        memory = ExecutorMemory()
        memory.add(ExecutionRecord("open_app", {"app_name": "notepad"}, success=True))
        ctx = memory.build_context_summary()   # 用于注入 Prompt
        errs = memory.recent_errors(n=3)       # 用于重试提示
    """

    def __init__(self, persist_path: Optional[str] = None):
        """
        Parameters
        ----------
        persist_path : str | None
            历史记录 JSON 文件路径。默认 logs/execution_history.json。
        """
        if persist_path is None:
            base = Path(__file__).parent.parent / "logs"
            base.mkdir(parents=True, exist_ok=True)
            persist_path = str(base / "execution_history.json")
        self._path = Path(persist_path)
        self._records: List[ExecutionRecord] = []
        self._load()

    # ──────────────────────────────────────────────
    # 公开 API
    # ──────────────────────────────────────────────

    def add(self, record: ExecutionRecord) -> None:
        """追加一条执行记录（同时写入内存和磁盘）。"""
        self._records.append(record)
        # 内存中只保留最近 N 条
        if len(self._records) > _SHORT_TERM_MAX:
            self._records = self._records[-_SHORT_TERM_MAX:]
        self._save()

    def recent_errors(self, n: int = 3) -> List[ExecutionRecord]:
        """返回最近 n 条失败记录，用于重试 Prompt 注入。"""
        errors = [r for r in self._records if not r.success]
        return errors[-n:]

    def recent_successes(self, n: int = 5) -> List[ExecutionRecord]:
        """返回最近 n 条成功记录，用于上下文参考。"""
        successes = [r for r in self._records if r.success]
        return successes[-n:]

    def build_context_summary(self, max_lines: int = 6) -> str:
        """构建供 Prompt 使用的上下文摘要字符串（中文）。"""
        if not self._records:
            return "（暂无执行历史）"

        lines = []
        for rec in self._records[-max_lines:]:
            status = "✓" if rec.success else "✗"
            ts = time.strftime("%H:%M:%S", time.localtime(rec.timestamp))
            params_str = json.dumps(rec.parameters, ensure_ascii=False)
            line = f"[{ts}] {status} {rec.skill_name}({params_str})"
            if not rec.success and rec.error_msg:
                line += f"  → 错误: {rec.error_msg[:80]}"
            lines.append(line)

        return "\n".join(lines)

    def error_pattern_hint(self) -> Optional[str]:
        """分析最近错误，返回简短的重试建议（用于 Prompt 注入）。

        当连续出现同一技能失败时，给出明确提示。
        """
        errors = self.recent_errors(n=5)
        if not errors:
            return None

        # 统计失败技能名频次
        from collections import Counter
        names = [r.skill_name for r in errors]
        counter = Counter(names)
        most_common_name, count = counter.most_common(1)[0]
        if count >= 2:
            return (
                f"注意：技能 '{most_common_name}' 最近已连续失败 {count} 次，"
                "请考虑换用其他技能或检查参数。"
            )
        return None

    def clear(self) -> None:
        """清空内存中的记录（不删除磁盘文件）。"""
        self._records.clear()

    # ──────────────────────────────────────────────
    # 持久化（内部）
    # ──────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            all_records = [ExecutionRecord.from_dict(d) for d in raw]
            # 仅保留最近 SHORT_TERM_MAX 条在内存
            self._records = all_records[-_SHORT_TERM_MAX:]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"ExecutorMemory: failed to load history from '{self._path}': {e}")
            self._records = []

    def _save(self) -> None:
        """原子写入持久化文件。"""
        # 读取磁盘上现有记录（与内存合并，保留更多历史）
        existing: List[dict] = []
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except (json.JSONDecodeError, OSError):
                existing = []

        # 合并：已有历史 + 当前内存记录（去重、保留顺序）
        existing_timestamps = {d["timestamp"] for d in existing}
        new_entries = [
            r.to_dict() for r in self._records
            if r.timestamp not in existing_timestamps
        ]
        merged = existing + new_entries
        # 裁剪到最大持久化条数
        if len(merged) > _PERSIST_MAX:
            merged = merged[-_PERSIST_MAX:]

        tmp_path = self._path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=2, ensure_ascii=False)
            tmp_path.replace(self._path)
        except OSError as e:
            logger.error(f"ExecutorMemory: failed to persist history: {e}")
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass
