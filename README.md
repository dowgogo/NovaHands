# NovaHands

![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python)
![License](https://img.shields.io/badge/License-MIT-green)
![Tests](https://img.shields.io/badge/Tests-54%2F54%20passed-brightgreen)

NovaHands 是一个智能桌面助手，具备以下核心功能：

- **基础自动化**：鼠标键盘模拟、屏幕元素识别、操作录制回放。
- **技能系统**：原生技能库 + OpenClaw 兼容技能库。
- **自然语言执行**：集成 OpenAI、Anthropic、Ollama 和本地模型（如 Qwen2.5-0.5B），理解用户指令并调用技能。
- **自学习进化**：记录用户操作，挖掘频繁模式，自动生成新技能。
- **强化学习与自我升级**：构建 RL 环境，利用本地模型作为策略网络，在线收集数据并微调，实现策略优化和技能进化。
- **多平台支持**：Windows、macOS、Linux 下获取前台窗口，跨平台鼠标键盘模拟。
- **API 服务**：FastAPI 提供 REST API，带认证，可被远程调用。
- **图形界面**：Tkinter 简易界面，提供技能管理、学习模式、确认对话框等。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

复制 `config.example.json` 为 `config.json`，根据需求填写 API 密钥等：

```bash
cp config.example.json config.json
```

### 3. 运行

| 模式 | 命令 |
|------|------|
| CLI 模式 | `python main.py` |
| GUI 模式 | `python main.py --gui` |
| 学习模式 | `python main.py --learn` |
| RL 数据收集 | `python main.py --rl` |
| API 服务 | `uvicorn api:app --host 127.0.0.1 --port 8000` |

## 项目结构

```
NovaHands/
├── README.md
├── LICENSE
├── config.example.json
├── requirements.txt
├── main.py
├── api.py
├── core/
│   ├── __init__.py
│   ├── controller.py
│   ├── recognizer.py
│   ├── safe_guard.py
│   └── nl_executor.py
├── models/
│   ├── __init__.py
│   ├── base_model.py
│   ├── openai_model.py
│   ├── anthropic_model.py
│   ├── ollama_model.py
│   ├── local_model.py
│   └── model_manager.py
├── skills/
│   ├── __init__.py
│   ├── base_skill.py
│   ├── skill_manager.py
│   ├── native/
│   │   ├── __init__.py
│   │   ├── send_email.py
│   │   └── open_app.py
│   └── claw_compat/
│       ├── __init__.py
│       └── claw_parser.py
├── learning/
│   ├── __init__.py
│   ├── action_recorder.py
│   ├── pattern_miner.py
│   └── skill_generator.py
├── rl/
│   ├── __init__.py
│   ├── environment.py
│   ├── policy.py
│   ├── collector.py
│   ├── trainer.py
│   └── evolution.py
├── gui/
│   ├── __init__.py
│   ├── confirm_dialog.py
│   └── main_window.py
├── utils/
│   ├── __init__.py
│   ├── logger.py
│   ├── config_loader.py
│   └── platform_utils.py
├── web/
│   └── index.html
└── tests/
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥 |
| `NOVAHANDS_API_KEY` | NovaHands REST API 认证密钥 |

## 测试

项目包含完整的虚拟测试套件，无需安装任何第三方依赖即可运行：

```bash
python tests/virtual_test.py
```

测试覆盖 11 个核心模块，共 54 个用例，全部通过。测试报告见 `tests/VIRTUAL_TEST_REPORT.md`。

## 许可证

MIT License
