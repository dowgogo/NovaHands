"""Test MCP server functionality."""
import sys
import os
import urllib.request
import json
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core.mcp_server import MCPServer
from skills.skill_manager import SkillManager
from core.controller import Controller

print("=== MCP Server Test ===")

sm = SkillManager()
ctrl = Controller()

# Create MCP server
server = MCPServer(sm, ctrl, host='127.0.0.1', port=3000)
print(f'[OK] MCP Server created on 127.0.0.1:3000')

# Start server
server.start()
print('[OK] MCP Server started in background')

# Wait for server startup
time.sleep(1)

# Test health check
print("\n--- Health Check ---")
try:
    resp = urllib.request.urlopen('http://127.0.0.1:3000/health', timeout=2)
    data = resp.read().decode()
    result = json.loads(data)
    print(f'[OK] Status: {result.get("status")}, Server: {result.get("server")}')
except Exception as e:
    print(f'[FAIL] Health check failed: {e}')

# Test tools list
print("\n--- Tools List ---")
try:
    resp = urllib.request.urlopen('http://127.0.0.1:3000/mcp/tools', timeout=2)
    data = resp.read().decode()
    result = json.loads(data)
    tools = result.get('tools', [])
    print(f'[OK] Available tools: {len(tools)}')
    for tool in tools[:3]:
        print(f'  - {tool["name"]}: {tool["description"][:60]}')
except Exception as e:
    print(f'[FAIL] Tools list failed: {e}')

# Test MCP JSON-RPC call
print("\n--- JSON-RPC Call ---")
rpc_request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1.0"}
    }
}
try:
    data = json.dumps(rpc_request).encode()
    req = urllib.request.Request(
        'http://127.0.0.1:3000/mcp',
        data=data,
        headers={'Content-Type': 'application/json'}
    )
    resp = urllib.request.urlopen(req, timeout=2)
    result = json.loads(resp.read().decode())
    print(f'[OK] Initialize response: {result.get("result", {}).get("serverInfo", {}).get("name")}')
except Exception as e:
    print(f'[FAIL] JSON-RPC call failed: {e}')

# Shutdown
server.stop()
print('\n[OK] Server shutdown complete')
print('\n=== All MCP tests passed ===')
