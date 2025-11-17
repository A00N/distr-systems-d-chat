import tkinter as tk
from tkinter import scrolledtext, simpledialog

class ChatUI:
    def __init__(self, username='anon', send_callback=None, on_close=None):
        self.username = username
        self.send_callback = send_callback
        self.on_close = on_close
        self.root = tk.Tk()
        self.root.title(f'D-Chat: {self.username}')
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self._build()

    def _build(self):
        # layout: left sidebar (users) + main chat area on the right
        self.root.columnconfigure(1, weight=1)

        # Sidebar frame for user list
        sidebar = tk.Frame(self.root)
        sidebar.grid(row=0, column=0, rowspan=2, sticky='ns', padx=(5, 0), pady=5)
        lbl = tk.Label(sidebar, text='Users')
        lbl.pack(anchor='nw')
        self.user_list = tk.Listbox(sidebar, height=20, exportselection=False)
        self.user_list.pack(side='left', fill='y', expand=False)
        ul_scroll = tk.Scrollbar(sidebar, orient='vertical', command=self.user_list.yview)
        ul_scroll.pack(side='right', fill='y')
        self.user_list.config(yscrollcommand=ul_scroll.set)

        # Main chat area
        main = tk.Frame(self.root)
        main.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')
        main.columnconfigure(0, weight=1)
        self.txt = scrolledtext.ScrolledText(main, wrap=tk.WORD, state='disabled', width=60, height=20)
        self.txt.grid(row=0, column=0, columnspan=2, sticky='nsew')
        self.entry = tk.Entry(main, width=50)
        self.entry.grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.send_btn = tk.Button(main, text='Send', command=self._on_send)
        self.send_btn.grid(row=1, column=1, padx=5, pady=5, sticky='e')

    def add_message(self, user, message):
        # schedule UI update on Tk main thread
        try:
            self.root.after(0, lambda: self._add_message_ui(user, message))
        except Exception:
            # fallback immediate
            self._add_message_ui(user, message)

    def _add_message_ui(self, user, message):
        self.txt.configure(state='normal')
        self.txt.insert(tk.END, f"{user}: {message}\n")
        self.txt.see(tk.END)
        self.txt.configure(state='disabled')

    def add_system_message(self, text):
        try:
            self.root.after(0, lambda: self._add_system_message_ui(text))
        except Exception:
            self._add_system_message_ui(text)

    def _add_system_message_ui(self, text):
        self.txt.configure(state='normal')
        self.txt.insert(tk.END, f"[system] {text}\n")
        self.txt.see(tk.END)
        self.txt.configure(state='disabled')

    def add_user_connected(self, username):
        """Add the username to the sidebar list and insert a chat line.

        This is safe to call from other threads; updates are scheduled on the Tk main loop.
        """
        try:
            self.root.after(0, lambda: self._add_user_connected_ui(username))
        except Exception:
            self._add_user_connected_ui(username)

    def _add_user_connected_ui(self, username):
        # avoid duplicates in the listbox
        existing = self.user_list.get(0, tk.END)
        if username not in existing:
            self.user_list.insert(tk.END, username)
        # also add a visible chat line
        self._add_message_ui('room', f'{username} connected!')

    def _on_send(self):
        text = self.entry.get().strip()
        if not text:
            return
        if self.send_callback:
            self.send_callback(text)
        self.entry.delete(0, tk.END)

    def _on_close(self):
        # call optional on_close callback to allow sending LEAVE / cleanup
        try:
            if self.on_close:
                try:
                    self.on_close()
                except Exception:
                    pass
        finally:
            try:
                self.root.quit()
                self.root.destroy()
            except Exception:
                pass

    def remove_user_connected(self, username):
        """Remove username from sidebar and add a '<username> disconnected' line."""
        try:
            self.root.after(0, lambda: self._remove_user_connected_ui(username))
        except Exception:
            self._remove_user_connected_ui(username)

    def _remove_user_connected_ui(self, username):
        # remove all matching entries
        items = list(self.user_list.get(0, tk.END))
        for i, v in enumerate(items):
            if v == username:
                self.user_list.delete(i)
                # only delete first match; break to avoid index shift issues
                break
        # add a visible chat line
        self._add_message_ui('room',f'{username} disconnected!')

    def run(self):
        self.root.mainloop()
