import hmac
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, field_validator
from typing import Dict, Any, Optional
from utils.logger import logger


# 操作级别的串行锁：Controller 操控真实鼠标键盘，并发执行会产生冲突
_execute_lock = asyncio.Lock()

# 全局资源，在 lifespan 中初始化
_resources: Dict[str, Any] = {}

# context 字段允许的键白名单，防止攻击者注入任意参数
_ALLOWED_CONTEXT_KEYS = {'current_app', 'window_title', 'user_name'}

# 不安全的默认 API Key 列表
_UNSAFE_KEYS = {'', 'default-key-change-me', 'your-api-key-here', 'changeme'}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    修复：将所有初始化逻辑移入 lifespan，避免 import 时崩溃。
    uvicorn 启动时执行，提供友好的错误信息。
    """
    try:
        from core.controller import Controller
        from core.nl_executor import NLExecutor
        from skills.skill_manager import SkillManager
        from models.model_manager import ModelManager
        from utils.config_loader import ConfigLoader

        config = ConfigLoader()
        api_key = config.get('api.api_key', '')

        # 检测不安全的 API Key
        if api_key in _UNSAFE_KEYS:
            raise RuntimeError(
                "API key is not configured or uses an unsafe default value. "
                "Please set NOVAHANDS_API_KEY environment variable or update config.json."
            )

        _resources['config'] = config
        _resources['api_key'] = api_key
        _resources['controller'] = Controller()
        _resources['skill_manager'] = SkillManager()
        _resources['model_manager'] = ModelManager()
        _resources['executor'] = NLExecutor(
            _resources['skill_manager'], _resources['model_manager']
        )
        logger.info("NovaHands API server initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize API server: {e}")
        raise

    yield  # 应用运行中

    # 清理资源（关闭时执行）
    _resources.clear()
    logger.info("NovaHands API server shut down")


app = FastAPI(lifespan=lifespan)


def verify_api_key(x_api_key: str = Header(...)):
    """使用 hmac.compare_digest 进行常数时间比较，防止时序侧信道攻击"""
    api_key = _resources.get('api_key', '')
    if not hmac.compare_digest(x_api_key, api_key):
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
    """
    修复：executor.execute() 是同步阻塞调用，通过 run_in_executor 放入线程池，
    避免阻塞 asyncio 事件循环导致其他请求无法处理。
    """
    executor = _resources.get('executor')
    controller = _resources.get('controller')
    if not executor or not controller:
        raise HTTPException(status_code=503, detail="Server not ready")

    async with _execute_lock:
        try:
            # Bug fix: get_event_loop() 在 Python 3.10+ Deprecated，3.12 移除
            # 在 async 上下文中应使用 get_running_loop()
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: executor.execute(request.command, controller, **request.context)
            )
            return {"status": "success"}
        except Exception as e:
            logger.error(f"API execution failed: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/skills", dependencies=[Depends(verify_api_key)])
async def list_skills():
    skill_manager = _resources.get('skill_manager')
    if not skill_manager:
        raise HTTPException(status_code=503, detail="Server not ready")
    return skill_manager.list_skills()


@app.get("/health")
async def health():
    return {"status": "ok", "ready": bool(_resources.get('executor'))}


# Run: uvicorn api:app --host 127.0.0.1 --port 8000
