import tkinter as tk
from tkinter import scrolledtext, simpledialog

class ChatUI:
    def __init__(self, username='anon', send_callback=None):
        self.username = username
        self.send_callback = send_callback
        self.root = tk.Tk()
        self.root.title(f'D-Chat: {self.username}')
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self._build()

    def _build(self):
        self.txt = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, state='disabled', width=60, height=20)
        self.txt.grid(row=0, column=0, columnspan=2, padx=5, pady=5)
        self.entry = tk.Entry(self.root, width=50)
        self.entry.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.send_btn = tk.Button(self.root, text='Send', command=self._on_send)
        self.send_btn.grid(row=1, column=1, padx=5, pady=5, sticky='e')

    def add_message(self, user, message):
        self.txt.configure(state='normal')
        self.txt.insert(tk.END, f"{user}: {message}\n")
        self.txt.see(tk.END)
        self.txt.configure(state='disabled')

    def add_system_message(self, text):
        self.txt.configure(state='normal')
        self.txt.insert(tk.END, f"[system] {text}\n")
        self.txt.see(tk.END)
        self.txt.configure(state='disabled')

    def _on_send(self):
        text = self.entry.get().strip()
        if not text:
            return
        if self.send_callback:
            self.send_callback(text)
        self.entry.delete(0, tk.END)

    def _on_close(self):
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()
