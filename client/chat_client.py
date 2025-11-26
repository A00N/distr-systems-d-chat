import threading
import time
import uuid
import requests
import tkinter as tk
from tkinter import simpledialog

from gui import ChatUI
from client import post_with_raft_redirects, get_with_raft_redirects

# In AWS, set this to your ALB URL, e.g. "https://my-alb-dns"
CLUSTER_URL = "http://127.0.0.1:9000"

MAX_ROOMS = 5


class ChatApp:
    def __init__(self, username=None):
        # If no username is given, pop up a small dialog first
        if username is None:
            root = tk.Tk()
            root.withdraw()
            username = simpledialog.askstring("Username", "Choose a name:")
            root.destroy()
            if not username:
                username = "anon"

        self.username = username

        # RAFT-backed state from server
        self._all_messages = []      # full log from /messages
        self._global_last_seen = 0   # index into _all_messages we have processed
        self._current_room = "general"
        self._rooms = {"general"}
        self._pending_ids = set()
        self._polling = True

        # Track active users and when we last saw them
        self._users = set()
        self._user_last_seen = {}

        self.ui = ChatUI(
            username=username,
            send_callback=self._on_send_text,
            on_close=self._on_close,
            room_change_callback=self._on_room_change,
            room_add_callback=self._on_room_add_requested,
            room_delete_callback=self._on_room_delete_requested,
        )

        self._current_room = "general"
        self.ui.set_rooms(sorted(self._rooms), select=self._current_room)

        # Show ourselves immediately in the Users list
        now = time.time()
        self._users.add(self.username)
        self._user_last_seen[self.username] = now
        self.ui.add_user_connected(self.username)

        # Start as "disconnected" until health check
        self.ui.set_status(False)
        self.ui.add_system_message(f"Starting client for user '{username}'")
        self.ui.add_system_message(f"Using cluster URL: {CLUSTER_URL}")
        self.ui.add_system_message(f"Current room: {self._current_room}")

        # Initial health check
        t = threading.Thread(target=self._initial_health_check, daemon=True)
        t.start()

        # Background polling of /messages
        poller = threading.Thread(target=self._poll_messages_loop, daemon=True)
        poller.start()

    # ---------- background health check ----------

    def _initial_health_check(self) -> None:
        try:
            r = requests.get(CLUSTER_URL + "/health", timeout=2)
            if r.status_code == 200:
                self.ui.add_system_message("Health check OK, cluster reachable.")
                self.ui.set_status(True)
            else:
                self.ui.add_system_message(f"Health check returned {r.status_code}.")
                self.ui.set_status(False)
        except Exception as e:
            self.ui.add_system_message(f"Health check failed: {e}")
            self.ui.set_status(False)

    # ---------- room handling ----------

    def _on_room_change(self, new_room: str):
        if not new_room:
            new_room = "general"
        self._current_room = new_room
        self.ui.add_system_message(f"Switched to room '{new_room}'")

        # Clear chat and redraw messages for this room from our local log
        self.ui.clear_messages()
        for m in self._all_messages:
            msg_type = m.get("type", "chat")
            if msg_type != "chat":
                continue
            room = m.get("room", "general")
            if room == self._current_room:
                user = m.get("user", "?")
                text = m.get("text", "")
                self.ui.add_message(user, text, style="normal")

    def _on_room_add_requested(self, room_name: str):
        if len(self._rooms) >= MAX_ROOMS and room_name not in self._rooms:
            self.ui.add_system_message(f"Cannot add room '{room_name}': max {MAX_ROOMS} rooms.")
            return
        if room_name in self._rooms:
            self.ui.add_system_message(f"Room '{room_name}' already exists.")
            return

        cmd = {"type": "room_add", "room": room_name, "user": self.username}
        self.ui.add_system_message(f"Requesting creation of room '{room_name}'...")
        t = threading.Thread(target=self._send_room_command, args=(cmd, "created"), daemon=True)
        t.start()

    def _on_room_delete_requested(self, room_name: str):
        if room_name == "general":
            self.ui.add_system_message("Cannot delete the 'general' room.")
            return
        if room_name not in self._rooms:
            self.ui.add_system_message(f"Room '{room_name}' does not exist.")
            return

        cmd = {"type": "room_delete", "room": room_name, "user": self.username}
        self.ui.add_system_message(f"Requesting deletion of room '{room_name}'...")
        t = threading.Thread(target=self._send_room_command, args=(cmd, "deleted"), daemon=True)
        t.start()

    def _send_room_command(self, cmd: dict, action_word: str):
        try:
            resp = post_with_raft_redirects(CLUSTER_URL, cmd)
            data = resp.json()
            if data.get("status") == "ok":
                self.ui.add_system_message(f"Room '{cmd.get('room')}' {action_word} (committed).")
                self.ui.set_status(True)
            else:
                self.ui.add_system_message(f"Room command failed: {data}")
                self.ui.set_status(False)
        except Exception as e:
            self.ui.add_system_message(f"Room command error: {e}")
            self.ui.set_status(False)

    # ---------- send handling ----------

    def _on_send_text(self, text: str) -> None:
        """Called from ChatUI (GUI thread) when the user hits Enter or Send."""
        room = self._current_room or "general"
        msg_id = str(uuid.uuid4())

        # Local gray echo
        self._pending_ids.add(msg_id)
        self.ui.add_pending_message(msg_id, self.username, text)

        payload = {
            "type": "chat",
            "user": self.username,
            "text": text,
            "room": room,
            "id": msg_id,
        }

        t = threading.Thread(target=self._send_message_background, args=(payload,))
        t.daemon = True
        t.start()

    def _send_message_background(self, payload: dict) -> None:
        try:
            # Previously we logged:
            #   self.ui.add_system_message("Sending message to cluster...")
            # Keep it quiet now.

            resp = post_with_raft_redirects(CLUSTER_URL, payload)

            data = resp.json()
            status = data.get("status")

            if status == "ok":
                # Previously:
                #   self.ui.add_system_message("Message committed via leader.")
                # Just flip status, no chat noise.
                self.ui.set_status(True)
            else:
                self.ui.add_system_message(f"Server responded with: {data}")
                self.ui.set_status(False)

        except Exception as e:
            # This covers redirect loops, long elections, network errors, etc.
            self.ui.add_system_message(f"Error sending message: {e}")
            self.ui.set_status(False)

    # ---------- background poll of /messages ----------

    def _poll_messages_loop(self) -> None:
        """
        Periodically fetch /messages from the cluster (with redirect handling)
        and:
          - update the room list based on room_add/room_delete events
          - show new chat messages for the current room
          - clear gray pending lines when their committed message arrives
          - update active users list
        """
        while self._polling:
            try:
                resp = get_with_raft_redirects(CLUSTER_URL, "/messages", timeout=2.0)
                msgs = resp.json()  # expected to be a list of dicts

                if isinstance(msgs, list):
                    old_len = len(self._all_messages)
                    self._all_messages = msgs

                    new_msgs = msgs[self._global_last_seen:]
                    for m in new_msgs:
                        msg_type = m.get("type", "chat")
                        user = m.get("user")

                        # --- Active users tracking ---
                        if user:
                            now = time.time()
                            if user not in self._users:
                                self._users.add(user)
                                self.ui.add_user_connected(user)
                            # update last-seen timestamp
                            self._user_last_seen[user] = now

                        if msg_type == "room_add":
                            room = m.get("room")
                            if room and room not in self._rooms:
                                self._rooms.add(room)
                                self.ui.set_rooms(sorted(self._rooms), select=self._current_room)

                        elif msg_type == "room_delete":
                            room = m.get("room")
                            if room and room in self._rooms and room != "general":
                                self._rooms.remove(room)
                                # If we are currently in the deleted room, move to general
                                if self._current_room == room:
                                    self._current_room = "general"
                                    self.ui.set_rooms(sorted(self._rooms), select=self._current_room)
                                    # redraw messages for general
                                    self._on_room_change(self._current_room)
                                else:
                                    self.ui.set_rooms(sorted(self._rooms), select=self._current_room)

                        elif msg_type == "chat":
                            # Remove pending gray echo if this message corresponds to one we sent
                            msg_id = m.get("id")
                            if msg_id and msg_id in self._pending_ids:
                                self._pending_ids.remove(msg_id)
                                self.ui.remove_pending_message(msg_id)

                            room = m.get("room", "general")
                            if room == self._current_room:
                                user_display = m.get("user", "?")
                                text = m.get("text", "")
                                self.ui.add_message(user_display, text, style="normal")
                    # After processing all new messages, prune inactive users
                    now = time.time()
                    inactive = [
                        u for u, last in self._user_last_seen.items()
                        if now - last > 300  # 5 minutes
                    ]

                    for u in inactive:
                        if u in self._users:
                            self._users.remove(u)
                            self.ui.remove_user_connected(u)
                        # remove from last-seen map
                        del self._user_last_seen[u]
                    self._global_last_seen = len(msgs)
                    if new_msgs:
                        self.ui.set_status(True)

            except Exception as e:
                self.ui.add_system_message(f"Error fetching messages: {e}")
                self.ui.set_status(False)

            time.sleep(1.0)

    # ---------- close ----------

    def _on_close(self) -> None:
        self._polling = False

    def run(self) -> None:
        self.ui.run()


if __name__ == "__main__":
    app = ChatApp(username=None)  # username will be asked via dialog
    app.run()
