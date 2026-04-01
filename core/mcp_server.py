"""mcp_server.py — Model Context Protocol (MCP) 工具服务器

将 NovaHands 的技能系统以 MCP 标准协议暴露，使任何支持 MCP 的
LLM（如 Claude、Cursor、Zed 等）都能直接调用 NovaHands 技能。

协议规范：https://modelcontextprotocol.io/specification
实现方式：JSON-RPC 2.0 over HTTP（简化版，不依赖官方 SDK）

端点：
  POST /mcp          — JSON-RPC dispatch
  GET  /mcp/tools    — 列出所有工具（MCP tools/list）
  GET  /health       — 健康检查

支持的 MCP 方法：
  initialize          — 握手
  tools/list          — 枚举技能列表
  tools/call          — 调用技能
  ping                — 心跳
"""

from __future__ import annotations

import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

logger = logging.getLogger("novahands")

# MCP 协议版本
_MCP_PROTOCOL_VERSION = "2024-11-05"
_SERVER_NAME = "NovaHands"
_SERVER_VERSION = "1.0.0"


class MCPHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器，实现 JSON-RPC 2.0 dispatch。"""

    # 由 MCPServer 注入
    skill_manager = None
    controller = None

    def log_message(self, fmt, *args):
        """重定向日志到 novahands logger，避免打印到 stderr。"""
        logger.debug(f"[MCP] {fmt % args}")

    def do_GET(self):
        if self.path == "/health":
            self._send_json({"status": "ok", "server": _SERVER_NAME})
        elif self.path == "/mcp/tools":
            self._send_json(self._build_tools_list())
        else:
            self._send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        if self.path != "/mcp":
            self._send_json({"error": "Not found"}, status=404)
            return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
        except json.JSONDecodeError as e:
            self._send_json(
                self._rpc_error(None, -32700, f"Parse error: {e}"),
                status=400,
            )
            return

        response = self._dispatch(req)
        self._send_json(response)

    # ──────────────────────────────────────────────
    # JSON-RPC dispatch
    # ──────────────────────────────────────────────

    def _dispatch(self, req: dict) -> dict:
        rpc_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        handlers = {
            "initialize": self._handle_initialize,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
        }

        handler = handlers.get(method)
        if handler is None:
            return self._rpc_error(rpc_id, -32601, f"Method not found: {method}")

        try:
            result = handler(params)
            return {"jsonrpc": "2.0", "id": rpc_id, "result": result}
        except MCPError as e:
            return self._rpc_error(rpc_id, e.code, e.message)
        except Exception as e:
            logger.error(f"[MCP] Internal error in method '{method}': {e}")
            return self._rpc_error(rpc_id, -32603, f"Internal error: {e}")

    # ──────────────────────────────────────────────
    # MCP 方法实现
    # ──────────────────────────────────────────────

    def _handle_initialize(self, params: dict) -> dict:
        """握手：返回服务器能力声明。"""
        return {
            "protocolVersion": _MCP_PROTOCOL_VERSION,
            "serverInfo": {
                "name": _SERVER_NAME,
                "version": _SERVER_VERSION,
            },
            "capabilities": {
                "tools": {"listChanged": False},
            },
        }

    def _handle_ping(self, params: dict) -> dict:
        return {}

    def _handle_tools_list(self, params: dict) -> dict:
        return self._build_tools_list()

    def _handle_tools_call(self, params: dict) -> dict:
        """执行技能调用。

        MCP tools/call 请求格式::

            {
                "name": "open_app",
                "arguments": {"app_name": "notepad"}
            }
        """
        name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not name:
            raise MCPError(-32602, "Missing required param: name")

        sm = MCPHandler.skill_manager
        if sm is None:
            raise MCPError(-32603, "SkillManager not initialized")

        skill = sm.get_skill(name)
        if skill is None:
            raise MCPError(-32602, f"Unknown tool: '{name}'")

        ctrl = MCPHandler.controller
        t_start = time.monotonic()
        try:
            result = sm.execute_skill(name, ctrl, **arguments)
            duration = time.monotonic() - t_start
            logger.info(f"[MCP] tools/call '{name}' OK ({duration:.2f}s)")

            # MCP content 格式
            content_text = (
                json.dumps(result, ensure_ascii=False)
                if result is not None
                else f"Skill '{name}' executed successfully"
            )
            return {
                "content": [{"type": "text", "text": content_text}],
                "isError": False,
            }
        except Exception as e:
            duration = time.monotonic() - t_start
            logger.error(f"[MCP] tools/call '{name}' FAILED ({duration:.2f}s): {e}")
            return {
                "content": [{"type": "text", "text": f"Error: {e}"}],
                "isError": True,
            }

    # ──────────────────────────────────────────────
    # 工具列表构建
    # ──────────────────────────────────────────────

    def _build_tools_list(self) -> dict:
        """将 SkillManager 的技能列表转换为 MCP tools 格式。"""
        sm = MCPHandler.skill_manager
        tools = []
        if sm:
            for name in sm.list_skills():
                skill = sm.get_skill(name)
                if skill is None:
                    continue

                # 构建 JSON Schema 格式的输入参数描述
                properties: Dict[str, Any] = {}
                required_params = []
                for param_name, param_type in (skill.parameters or {}).items():
                    json_type = _py_type_to_json_schema(param_type)
                    properties[param_name] = {"type": json_type}
                    required_params.append(param_name)

                tool: Dict[str, Any] = {
                    "name": name,
                    "description": skill.description or "",
                    "inputSchema": {
                        "type": "object",
                        "properties": properties,
                    },
                }
                if required_params:
                    tool["inputSchema"]["required"] = required_params
                tools.append(tool)

        return {"tools": tools}

    # ──────────────────────────────────────────────
    # 响应工具
    # ──────────────────────────────────────────────

    def _send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @staticmethod
    def _rpc_error(rpc_id: Optional[Any], code: int, message: str) -> dict:
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": code, "message": message},
        }


class MCPError(Exception):
    """MCP 方法级错误（映射到 JSON-RPC error response）。"""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class MCPServer:
    """NovaHands MCP 服务器（后台线程运行）。

    Usage::

        server = MCPServer(skill_manager, controller, port=7688)
        server.start()        # 非阻塞，后台线程
        ...
        server.stop()
    """

    def __init__(self, skill_manager, controller, host: str = "127.0.0.1",
                 port: int = 7688):
        self.host = host
        self.port = port
        self._skill_manager = skill_manager
        self._controller = controller
        self._httpd: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """在后台线程中启动 MCP HTTP 服务器。"""
        # 注入依赖到 Handler 类（handler 实例由 HTTPServer 创建，无法直接传参）
        MCPHandler.skill_manager = self._skill_manager
        MCPHandler.controller = self._controller

        self._httpd = HTTPServer((self.host, self.port), MCPHandler)
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            name="mcp-server",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"[MCP] Server started at http://{self.host}:{self.port}/mcp "
            f"(tools endpoint: http://{self.host}:{self.port}/mcp/tools)"
        )

    def stop(self) -> None:
        """停止 MCP 服务器。"""
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
        logger.info("[MCP] Server stopped")

    @property
    def is_running(self) -> bool:
        return self._httpd is not None and self._thread is not None and self._thread.is_alive()

    def url(self) -> str:
        return f"http://{self.host}:{self.port}/mcp"


def _py_type_to_json_schema(py_type: str) -> str:
    """将 NovaHands 技能参数类型字符串转换为 JSON Schema type。"""
    mapping = {
        "str": "string",
        "string": "string",
        "int": "integer",
        "integer": "integer",
        "float": "number",
        "number": "number",
        "bool": "boolean",
        "boolean": "boolean",
        "list": "array",
        "dict": "object",
        "any": "string",  # 降级为 string
    }
    return mapping.get(str(py_type).lower(), "string")
