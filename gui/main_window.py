import time
import tkinter as tk
from tkinter import scrolledtext, ttk
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
        self.root.geometry("640x480")
        self.root.configure(bg="#1e1e2e")

        # ── 输入区 ──────────────────────────────────
        input_frame = tk.Frame(self.root, bg="#1e1e2e")
        input_frame.pack(pady=(10, 4), padx=12, fill=tk.X)

        tk.Label(
            input_frame, text="指令", bg="#1e1e2e", fg="#cdd6f4",
            font=("Segoe UI", 9, "bold")
        ).pack(anchor=tk.W)

        self.text_input = scrolledtext.ScrolledText(
            input_frame, height=4,
            bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4",
            relief=tk.FLAT, font=("Segoe UI", 10),
            borderwidth=1
        )
        self.text_input.pack(fill=tk.X, pady=(2, 0))
        # Ctrl+Enter 快捷键执行
        self.text_input.bind("<Control-Return>", lambda e: self.execute())

        # ── 按钮 + 状态栏 ────────────────────────────
        ctrl_frame = tk.Frame(self.root, bg="#1e1e2e")
        ctrl_frame.pack(pady=4, padx=12, fill=tk.X)

        self.btn_execute = tk.Button(
            ctrl_frame, text="▶ 执行 (Ctrl+Enter)",
            command=self.execute,
            bg="#89b4fa", fg="#1e1e2e", activebackground="#74c7ec",
            relief=tk.FLAT, padx=12, pady=4,
            font=("Segoe UI", 9, "bold"), cursor="hand2"
        )
        self.btn_execute.pack(side=tk.LEFT)

        self.btn_clear = tk.Button(
            ctrl_frame, text="清空",
            command=self._clear_output,
            bg="#45475a", fg="#cdd6f4", activebackground="#585b70",
            relief=tk.FLAT, padx=10, pady=4,
            font=("Segoe UI", 9), cursor="hand2"
        )
        self.btn_clear.pack(side=tk.LEFT, padx=(6, 0))

        # 状态标签：显示 "就绪 / 执行中... / ✓ 完成"
        self.status_var = tk.StringVar(value="就绪")
        self.status_label = tk.Label(
            ctrl_frame, textvariable=self.status_var,
            bg="#1e1e2e", fg="#a6e3a1",
            font=("Segoe UI", 9)
        )
        self.status_label.pack(side=tk.RIGHT)

        # 进度条（indeterminate，执行中滚动）
        self.progress = ttk.Progressbar(
            self.root, mode="indeterminate", length=200
        )
        self.progress.pack(padx=12, fill=tk.X)

        # ── 输出区 ───────────────────────────────────
        output_frame = tk.Frame(self.root, bg="#1e1e2e")
        output_frame.pack(pady=(6, 10), padx=12, fill=tk.BOTH, expand=True)

        tk.Label(
            output_frame, text="输出", bg="#1e1e2e", fg="#cdd6f4",
            font=("Segoe UI", 9, "bold")
        ).pack(anchor=tk.W)

        self.text_output = scrolledtext.ScrolledText(
            output_frame, height=14,
            bg="#181825", fg="#cdd6f4", insertbackground="#cdd6f4",
            relief=tk.FLAT, font=("Consolas", 9),
            state=tk.DISABLED
        )
        self.text_output.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

        # 颜色 tag
        self.text_output.tag_config("info",    foreground="#89b4fa")
        self.text_output.tag_config("success", foreground="#a6e3a1")
        self.text_output.tag_config("warning", foreground="#f9e2af")
        self.text_output.tag_config("error",   foreground="#f38ba8")
        self.text_output.tag_config("dim",     foreground="#6c7086")
        self.text_output.tag_config("cmd",     foreground="#cba6f7", font=("Consolas", 9, "bold"))

    # ── 私有工具方法 ─────────────────────────────────

    def _append_output(self, text: str, tag: str = ""):
        """线程安全地向输出区追加带颜色的文字"""
        def _insert():
            self.text_output.config(state=tk.NORMAL)
            if tag:
                self.text_output.insert(tk.END, text, tag)
            else:
                self.text_output.insert(tk.END, text)
            self.text_output.see(tk.END)
            self.text_output.config(state=tk.DISABLED)
        self.root.after(0, _insert)

    def _set_btn_state(self, state: str):
        """线程安全地切换按钮状态"""
        self.root.after(0, lambda: self.btn_execute.config(state=state))

    def _set_status(self, text: str, color: str = "#a6e3a1"):
        """线程安全地更新状态标签"""
        def _update():
            self.status_var.set(text)
            self.status_label.config(fg=color)
        self.root.after(0, _update)

    def _start_progress(self):
        self.root.after(0, self.progress.start)

    def _stop_progress(self):
        self.root.after(0, self.progress.stop)

    def _clear_output(self):
        self.text_output.config(state=tk.NORMAL)
        self.text_output.delete("1.0", tk.END)
        self.text_output.config(state=tk.DISABLED)
        self.status_var.set("就绪")

    # ── 执行逻辑 ─────────────────────────────────────

    def execute(self):
        cmd = self.text_input.get("1.0", tk.END).strip()
        if not cmd:
            return

        # 禁用按钮防止并发执行
        self.btn_execute.config(state=tk.DISABLED)
        self._append_output(f"\n>>> {cmd}\n", "cmd")
        self._append_output("⏳ 正在解析指令…\n", "dim")
        self._set_status("执行中…", "#f9e2af")
        self._start_progress()

        def run():
            t0 = time.perf_counter()
            try:
                result = self.executor.execute(cmd, self.controller)
                elapsed = time.perf_counter() - t0

                if result:
                    self._append_output(
                        f"✓ 已执行技能: {result}（耗时 {elapsed:.2f}s）\n",
                        "success"
                    )
                    self._set_status(f"✓ {result} 完成", "#a6e3a1")
                else:
                    self._append_output(
                        f"⚠ 未找到匹配技能，请检查指令或配置 LLM（耗时 {elapsed:.2f}s）\n",
                        "warning"
                    )
                    self._set_status("⚠ 未匹配", "#f9e2af")

            except Exception as e:
                elapsed = time.perf_counter() - t0
                logger.error(f"GUI execute error: {e}")
                self._append_output(
                    f"✗ 执行失败: {type(e).__name__}: {e}（耗时 {elapsed:.2f}s）\n",
                    "error"
                )
                self._set_status(f"✗ 错误: {type(e).__name__}", "#f38ba8")
            finally:
                self._stop_progress()
                self._set_btn_state(tk.NORMAL)

        threading.Thread(target=run, daemon=True).start()

    def run(self):
        self.root.mainloop()
