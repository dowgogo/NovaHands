import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
from core.nl_executor import NLExecutor
from skills.skill_manager import SkillManager
from models.model_manager import ModelManager
from core.controller import Controller
from utils.logger import logger


class MainWindow:
    def __init__(self, controller, skill_manager, model_manager):
        self.controller = controller
        self.skill_manager = skill_manager
        self.model_manager = model_manager
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

    def execute(self):
        cmd = self.text_input.get("1.0", tk.END).strip()
        if not cmd:
            return
        self.text_output.insert(tk.END, f">>> {cmd}\n")
        self.text_output.see(tk.END)

        def run():
            try:
                self.executor.execute(cmd, self.controller)
                self.text_output.insert(tk.END, "执行成功\n")
            except Exception as e:
                self.text_output.insert(tk.END, f"错误: {e}\n")
            self.text_output.see(tk.END)

        threading.Thread(target=run, daemon=True).start()

    def run(self):
        self.root.mainloop()
