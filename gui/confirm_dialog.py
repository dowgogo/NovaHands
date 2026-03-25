import tkinter as tk
import time
import threading


def confirm_operation(message: str, timeout: int = 30) -> bool:
    result = [False]
    root = tk.Tk()
    root.title("NovaHands 安全确认")
    root.geometry("400x150")
    label = tk.Label(root, text=message, wraplength=350)
    label.pack(pady=10)

    def on_yes():
        result[0] = True
        root.destroy()

    def on_no():
        result[0] = False
        root.destroy()

    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="允许", command=on_yes, width=10).pack(side=tk.LEFT, padx=10)
    tk.Button(btn_frame, text="拒绝", command=on_no, width=10).pack(side=tk.LEFT, padx=10)

    def auto_close():
        time.sleep(timeout)
        if root.winfo_exists():
            root.destroy()

    threading.Thread(target=auto_close, daemon=True).start()
    root.mainloop()
    return result[0]
