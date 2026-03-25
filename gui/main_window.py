import tkinter as tk
from tkinter import scrolledtext
import threading
from core.nl_executor import NLExecutor
from utils.logger import logger


class MainWindow:
    def __init__(self, controller, skill_manager, model_manager):
        self.controller = controller
        self.skill_manager = skill_manager
        self.model_manager = model_manager
        # 复用外部传入的 executor，不在内部重复创建（避免二次加载本地模型）
        self.executor = NLExecutor(skill_manager, model_manager)
        self.root = tk.Tk()
        self.root.title("NovaHands")
        self.root.geometry("600x400")

        self.text_input = scrolledtext.ScrolledText(self.root, height=5)
        self.text_input.pack(pady=10, padx=10, fill=tk.X)

        self.btn_execute = tk.Button(self.root, text="执行", command=self.execute)
        self.btn_execute.pack(pady=5)

        self.text_output = scrolledtext.ScrolledText(self.root, height=15)
        self.text_output.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

    def _append_output(self, text: str):
        """线程安全地向输出区追加文字（通过 root.after 调度到主线程）"""
        self.root.after(0, lambda: (
            self.text_output.insert(tk.END, text),
            self.text_output.see(tk.END)
        ))

    def _set_btn_state(self, state: str):
        """线程安全地切换按钮状态"""
        self.root.after(0, lambda: self.btn_execute.config(state=state))

    def execute(self):
        cmd = self.text_input.get("1.0", tk.END).strip()
        if not cmd:
            return

        # 禁用按钮防止并发执行
        self.btn_execute.config(state=tk.DISABLED)
        self._append_output(f">>> {cmd}\n")

        def run():
            try:
                self.executor.execute(cmd, self.controller)
                self._append_output("执行成功\n")
            except Exception as e:
                logger.error(f"GUI execute error: {e}")
                self._append_output(f"错误: {e}\n")
            finally:
                # 执行完毕后恢复按钮
                self._set_btn_state(tk.NORMAL)

        threading.Thread(target=run, daemon=True).start()

    def run(self):
        self.root.mainloop()
