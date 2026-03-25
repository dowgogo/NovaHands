"""rl/utils.py — RL 模块公共工具函数

将原先在 policy.py 和 trainer.py 中重复定义的 _format_state() 提取到此处，
所有 RL 模块统一从这里导入。
"""


def format_state(state: dict) -> str:
    """将 NovaHandsEnv 的 observation dict 格式化为 LLM 可理解的文本。

    Parameters
    ----------
    state : dict
        包含以下键：
        - current_app    : str  当前前台应用名
        - last_user_input: str  上一条用户指令
        - last_skill     : str  上一个执行的技能名
        - last_result    : bool 上一次执行是否成功

    Returns
    -------
    str
        格式化后的状态描述文本。
    """
    return (
        f"当前应用: {state.get('current_app', '未知')}\n"
        f"上一条指令: {state.get('last_user_input', '')}\n"
        f"上一技能: {state.get('last_skill', '')}\n"
        f"结果: {'成功' if state.get('last_result') else '失败'}"
    )
