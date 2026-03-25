import tkinter as tk
from tkinter import messagebox
import threading


def confirm_operation(message: str, timeout: int = 30) -> bool:
    """
    弹出确认对话框，用户点击允许/拒绝，或超时后自动拒绝。
    使用 Toplevel 而非 Tk()，避免多 Tk 实例导致事件循环冲突。
    若 tkinter 不可用（headless 环境），直接返回 False。
    """
    try:
        # 使用 threading.Event 协调主线程与超时线程，避免竞态
        closed_event = threading.Event()
        result = [False]

        # 尝试获取或创建根窗口
        try:
            root = tk._default_root  # 已有主窗口时复用
            if root is None:
                raise RuntimeError("no default root")
            dialog = tk.Toplevel(root)
        except Exception:
            # 无主窗口时创建临时根窗口（隐藏）
            root = tk.Tk()
            root.withdraw()
            dialog = tk.Toplevel(root)
            _own_root = root
        else:
            _own_root = None

        dialog.title("NovaHands 安全确认")
        dialog.geometry("400x150")
        dialog.grab_set()  # 模态对话框

        label = tk.Label(dialog, text=message, wraplength=350)
        label.pack(pady=10)

        def on_yes():
            result[0] = True
            closed_event.set()
            dialog.destroy()
            if _own_root:
                _own_root.destroy()

        def on_no():
            result[0] = False
            closed_event.set()
            dialog.destroy()
            if _own_root:
                _own_root.destroy()

        btn_frame = tk.Frame(dialog)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="允许", command=on_yes, width=10).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_frame, text="拒绝", command=on_no, width=10).pack(side=tk.LEFT, padx=10)

        def auto_close():
            # 等待超时，若用户未操作则通过 after() 安全关闭
            if not closed_event.wait(timeout):
                closed_event.set()
                dialog.after(0, on_no)

        threading.Thread(target=auto_close, daemon=True).start()

        if _own_root:
            _own_root.mainloop()
        else:
            dialog.wait_window()

        return result[0]

    except Exception:
        # headless 或 tkinter 不可用时，默认拒绝并记录
        import logging
        logging.getLogger('novahands').warning(
            "confirm_operation: tkinter unavailable (headless?), defaulting to False"
        )
        return False
