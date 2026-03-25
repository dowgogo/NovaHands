import hmac
import asyncio
import os
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, field_validator
from typing import Dict, Any, Optional
from core.controller import Controller
from core.nl_executor import NLExecutor
from skills.skill_manager import SkillManager
from models.model_manager import ModelManager
from utils.config_loader import ConfigLoader
from utils.logger import logger

app = FastAPI()

config = ConfigLoader()
controller = Controller()
skill_manager = SkillManager()
model_manager = ModelManager()
executor = NLExecutor(skill_manager, model_manager)

# 操作级别的串行锁：Controller 操控真实鼠标键盘，并发执行会产生冲突
_execute_lock = asyncio.Lock()

API_KEY = config.get('api.api_key', '')

# 启动时强制检测 API Key 配置，拒绝使用空值或默认占位符
_UNSAFE_KEYS = {'', 'default-key-change-me', 'your-api-key-here', 'changeme'}
if API_KEY in _UNSAFE_KEYS:
    raise RuntimeError(
        "API key is not configured or uses an unsafe default value. "
        "Please set NOVAHANDS_API_KEY environment variable or update config.json."
    )

# context 字段允许的键白名单，防止攻击者注入任意参数
_ALLOWED_CONTEXT_KEYS = {'current_app', 'window_title', 'user_name'}


def verify_api_key(x_api_key: str = Header(...)):
    # 使用 hmac.compare_digest 进行常数时间比较，防止时序侧信道攻击
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API Key")


class ExecuteRequest(BaseModel):
    command: str
    context: Dict[str, Any] = {}

    @field_validator('command')
    @classmethod
    def command_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("command must not be empty")
        return v

    @field_validator('context')
    @classmethod
    def context_whitelist(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """只保留白名单中的 context 键，防止参数注入"""
        return {k: val for k, val in v.items() if k in _ALLOWED_CONTEXT_KEYS}


@app.post("/execute", dependencies=[Depends(verify_api_key)])
async def execute(request: ExecuteRequest):
    # 使用锁确保同一时刻只有一个请求在操控鼠标键盘
    async with _execute_lock:
        try:
            executor.execute(request.command, controller, **request.context)
            return {"status": "success"}
        except Exception as e:
            logger.error(f"API execution failed: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/skills", dependencies=[Depends(verify_api_key)])
async def list_skills():
    return skill_manager.list_skills()


# Run: uvicorn api:app --host 127.0.0.1 --port 8000

