import socket
import threading
import json
import tkinter as tk
from tkinter import ttk, messagebox, colorchooser
import time
import struct
import select

DISCOVERY_PORT = 9998

def send_msg(sock: socket.socket, data: dict) -> bool:
    try:
        payload = json.dumps(data).encode('utf-8')
        sock.sendall(len(payload).to_bytes(4, 'big') + payload)
        return True
    except Exception:
        return False

def recv_msg(sock: socket.socket) -> dict | None:
    try:
        raw_len = _recv_exact(sock, 4)
        if raw_len is None:
            return None
        n = int.from_bytes(raw_len, 'big')
        raw = _recv_exact(sock, n)
        if raw is None:
            return None
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return None

def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
    buf = b''
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except Exception:
            return None
        if not chunk:
            return None
        buf += chunk
    return buf

def get_all_local_ips() -> list[str]:
    """
    Mengumpulkan SEMUA alamat IPv4 lokal milik device ini, dari SEMUA network
    adapter yang aktif (WiFi, Ethernet, VirtualBox Host-Only, VMware vEthernet,
    Docker/WSL, Hamachi, VPN, Tailscale, dll) -- bukan hanya satu IP yang
    "ditebak" lewat rute default seperti sebelumnya.

    ROOT CAUSE auto-detect gagal: dulu broadcast UDP dikirim lewat socket yang
    tidak diikat (bind) ke interface tertentu, sehingga OS bebas memilih lewat
    adapter MANA paket itu keluar. Kalau ada adapter virtual/VPN yang kebetulan
    jadi rute default, broadcast bisa keluar lewat adapter virtual itu dan TIDAK
    PERNAH sampai ke WiFi/hotspot yang sebenarnya dipakai -- walau dua device
    sebenarnya satu subnet. Dengan mengetahui semua IP lokal di sini, kita bisa
    kirim broadcast secara eksplisit lewat SETIAP adapter (lihat _auto_detect).
    """
    ips: set[str] = set()

    try:
        hostname = socket.gethostname()
        _, _, addr_list = socket.gethostbyname_ex(hostname)
        for ip in addr_list:
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass

    # Probe beberapa tujuan umum: trik ini TIDAK mengirim data apa pun (UDP
    # connect() cuma menentukan rute), tapi membantu memunculkan IP adapter
    # lain yang kadang tidak ikut terdaftar lewat hostname di atas.
    probe_targets = ["8.8.8.8", "1.1.1.1", "192.168.1.1", "192.168.0.1", "192.168.56.1"]
    for target in probe_targets:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.2)
            s.connect((target, 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                ips.add(ip)
        except Exception:
            pass

    return list(ips)

BG_DARK    = "#1e1e2e"
BG_MID     = "#2a2a3e"
BG_CARD    = "#313147"
ACCENT     = "#7c6af7"
ACCENT2    = "#f7a66a"
SUCCESS    = "#5dca8a"
DANGER     = "#e05c7a"
TEXT_MAIN  = "#e8e8f4"
TEXT_DIM   = "#9090b0"
FONT_TITLE = ("Segoe UI", 22, "bold")
FONT_HEAD  = ("Segoe UI", 14, "bold")
FONT_BODY  = ("Segoe UI", 11)
FONT_MONO  = ("Consolas", 11)

def styled_btn(parent, text, cmd, bg=ACCENT, fg=TEXT_MAIN, font=FONT_BODY, padx=14, pady=6, **kw):
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                  font=font, relief="flat", cursor="hand2",
                  activebackground=ACCENT2, activeforeground="#000",
                  padx=padx, pady=pady, **kw)
    return b

def styled_entry(parent, show=None, width=26, **kw):
    e = tk.Entry(parent, bg=BG_MID, fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                 font=FONT_BODY, relief="flat", width=width, show=show, **kw)
    return e

def label(parent, text, font=FONT_BODY, fg=TEXT_MAIN, **kw):
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=fg,
                    font=font, **kw)

class AuthScreen(tk.Frame):
    def __init__(self, master, on_auth):
        super().__init__(master, bg=BG_DARK)
        self.on_auth = on_auth
        self._build()

    def _build(self):
        self.pack(fill="both", expand=True)
        card = tk.Frame(self, bg=BG_CARD, padx=40, pady=36)
        card.place(relx=0.5, rely=0.5, anchor="center")

        label(card, "🎨 Drawtic.io", font=FONT_TITLE, fg=ACCENT).pack(pady=(0,4))
        label(card, "Draw & Guess with friends!", fg=TEXT_DIM).pack(pady=(0,20))

        host_frame = tk.Frame(card, bg=BG_CARD)
        host_frame.pack(fill="x", anchor="w")
        label(host_frame, "Host IP").pack(side="left")
        styled_btn(host_frame, "🔍 Auto-Detect", self._auto_detect, 
                   bg=BG_MID, font=("Segoe UI", 8), padx=8, pady=2).pack(side="right")
                   
        self.host_var = tk.StringVar(value="")
        styled_entry(card, textvariable=self.host_var).pack(fill="x", pady=(0,8))

        label(card, "Username").pack(anchor="w")
        self.user_var = tk.StringVar()
        styled_entry(card, textvariable=self.user_var).pack(fill="x", pady=(0,8))

        label(card, "Password").pack(anchor="w")
        self.pass_var = tk.StringVar()
        styled_entry(card, textvariable=self.pass_var, show="•").pack(fill="x", pady=(0,16))

        self.status = label(card, "", fg=DANGER)
        self.status.pack(pady=(0,8))

        btn_row = tk.Frame(card, bg=BG_CARD)
        btn_row.pack(fill="x")
        styled_btn(btn_row, "Login",    self._login,    bg=ACCENT).pack(side="left", expand=True, fill="x", padx=(0,4))
        styled_btn(btn_row, "Register", self._register, bg=BG_MID).pack(side="left", expand=True, fill="x", padx=(4,0))

    def _auto_detect(self):
        self.status.config(text="Searching local network...", fg=TEXT_DIM)
        self.update() 

        sockets: list[socket.socket] = []
        found_ip = None
        try:
            # KODE INI GA GW SENTUH SAMA SEKALI -> diganti jadi multi-interface
            # karena 1 socket "default" saja terbukti tidak cukup di Windows
            # ketika ada banyak adapter (VirtualBox/VMware/Hamachi/VPN/Tailscale).
            local_ips = get_all_local_ips()

            for ip in local_ips:
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                    # Bind ke IP adapter spesifik ini supaya paket broadcast
                    # benar-benar keluar lewat adapter tersebut, bukan lewat
                    # adapter "default" pilihan OS yang bisa saja salah.
                    s.bind((ip, 0))
                    s.setblocking(False)
                    sockets.append(s)
                except Exception:
                    continue

            # Fallback: kalau semua bind ke IP spesifik gagal (jarang terjadi),
            # tetap coba cara lama supaya fitur tidak mati total.
            if not sockets:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.bind(('', 0))
                s.setblocking(False)
                sockets.append(s)

            # Target: broadcast umum + broadcast langsung tiap subnet
            # (mis. 192.168.1.255) dari setiap adapter yang ditemukan, supaya
            # tetap jalan walau salah satu jenis broadcast difilter router.
            targets = {"255.255.255.255"}
            for ip in local_ips:
                octets = ip.split(".")
                if len(octets) == 4:
                    targets.add(f"{octets[0]}.{octets[1]}.{octets[2]}.255")

            for s in sockets:
                for t in targets:
                    try:
                        s.sendto(b"DISCOVER_SKRIBBL_SERVER", (t, DISCOVERY_PORT))
                    except Exception:
                        pass

            deadline = time.time() + 2.0
            while sockets and time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                ready, _, _ = select.select(sockets, [], [], remaining)
                if not ready:
                    break
                for s in ready:
                    try:
                        data, addr = s.recvfrom(1024)
                    except Exception:
                        continue
                    if data.startswith(b"SKRIBBL_SERVER_HERE"):
                        decoded = data.decode('utf-8', errors='ignore')
                        parts = decoded.split(":")
                        found_ip = parts[1] if len(parts) > 1 else addr[0]
                        break
                if found_ip:
                    break

            if found_ip:
                self.host_var.set(found_ip) 
                self.status.config(text=f"Server found at {found_ip}!", fg=SUCCESS)
            else:
                self.status.config(text="No server found on LAN.", fg=DANGER)
        except Exception as e:
            self.status.config(text=f"Network error: {e}", fg=DANGER)
        finally:
            for s in sockets:
                try:
                    s.close()
                except Exception:
                    pass

    def _connect(self) -> socket.socket | None:
        host = self.host_var.get().strip() or "127.0.0.1"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, 9999))
            sock.settimeout(None)
            return sock
        except Exception as e:
            self.status.config(text=f"Cannot connect: {e}")
            return None

    def _login(self):
        sock = self._connect()
        if not sock:
            return
        send_msg(sock, {"action":"login",
                        "username": self.user_var.get().strip(),
                        "password": self.pass_var.get()})
        resp = recv_msg(sock)
        if resp and resp.get("ok"):
            self.on_auth(sock, self.user_var.get().strip(), resp.get("message",""))
        else:
            sock.close()
            self.status.config(text=resp.get("message","Login failed") if resp else "No response")

    def _register(self):
        sock = self._connect()
        if not sock:
            return
        send_msg(sock, {"action":"register",
                        "username": self.user_var.get().strip(),
                        "password": self.pass_var.get()})
        resp = recv_msg(sock)
        if resp and resp.get("ok"):
            send_msg(sock, {"action":"login",
                            "username": self.user_var.get().strip(),
                            "password": self.pass_var.get()})
            resp2 = recv_msg(sock)
            if resp2 and resp2.get("ok"):
                self.on_auth(sock, self.user_var.get().strip(), "Registered & logged in!")
                return
        sock.close()
        self.status.config(text=resp.get("message","Register failed") if resp else "No response")


class RoomScreen(tk.Frame):
    def __init__(self, master, sock: socket.socket, username: str, on_join, on_logout):
        super().__init__(master, bg=BG_DARK)
        self.sock = sock
        self.username = username
        self.on_join = on_join
        self.on_logout = on_logout
        self._build()
        self.after(100, self._refresh_rooms)

    def _build(self):
        self.pack(fill="both", expand=True)
        card = tk.Frame(self, bg=BG_CARD, padx=40, pady=36)
        card.place(relx=0.5, rely=0.5, anchor="center")

        header = tk.Frame(card, bg=BG_CARD)
        header.pack(fill="x", pady=(0, 20))
        
        title_box = tk.Frame(header, bg=BG_CARD)
        title_box.pack(side="left")
        label(title_box, "🏠 Lobby", font=FONT_TITLE, fg=ACCENT).pack(anchor="w")
        label(title_box, f"Welcome, {self.username}!", fg=TEXT_DIM).pack(anchor="w", pady=(2,0))

        styled_btn(header, "🚪 Log Out", self._logout, bg=DANGER, font=("Segoe UI", 9), padx=10, pady=4).pack(side="right", anchor="ne")

        list_frame = tk.Frame(card, bg=BG_MID)
        list_frame.pack(fill="x", pady=(0, 10))
        
        self.room_listbox = tk.Listbox(list_frame, bg=BG_MID, fg=TEXT_MAIN, 
                                       font=FONT_BODY, height=6, relief="flat", highlightthickness=0)
        self.room_listbox.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        
        scroll = tk.Scrollbar(list_frame, command=self.room_listbox.yview)
        scroll.pack(side="right", fill="y")
        self.room_listbox.config(yscrollcommand=scroll.set)

        btn_row1 = tk.Frame(card, bg=BG_CARD)
        btn_row1.pack(fill="x", pady=(0, 16))
        styled_btn(btn_row1, "Join Selected", self._join_room, bg=SUCCESS).pack(side="left", expand=True, fill="x", padx=(0,4))
        styled_btn(btn_row1, "🔄 Refresh", self._refresh_rooms, bg=BG_MID).pack(side="left", expand=True, fill="x", padx=(4,0))

        label(card, "Create New Room").pack(anchor="w")
        self.new_room_var = tk.StringVar()
        
        create_row = tk.Frame(card, bg=BG_CARD)
        create_row.pack(fill="x", pady=(0, 8))
        
        styled_entry(create_row, textvariable=self.new_room_var, width=16).pack(side="left", fill="x", expand=True, padx=(0, 4), ipady=4)
        styled_btn(create_row, "Create", self._create_room, bg=ACCENT).pack(side="left")

        self.status = label(card, "", fg=DANGER)
        self.status.pack(pady=(0,8))

    def _refresh_rooms(self):
        send_msg(self.sock, {"action": "get_rooms"})
        resp = recv_msg(self.sock)
        if resp and resp.get("action") == "room_list":
            self.room_listbox.delete(0, tk.END)
            rooms = resp.get("rooms", [])
            if not rooms:
                self.room_listbox.insert(tk.END, "No active rooms...")
            else:
                for r in rooms:
                    self.room_listbox.insert(tk.END, r)

    def _create_room(self):
        name = self.new_room_var.get().strip()
        if name:
            send_msg(self.sock, {"action": "create_room", "room_name": name})
            self._wait_for_join()

    def _join_room(self):
        sel = self.room_listbox.curselection()
        if not sel:
            self.status.config(text="Select a room first!")
            return
        room_name = self.room_listbox.get(sel[0])
        if room_name == "No active rooms...":
            return
            
        send_msg(self.sock, {"action": "join_room", "room_name": room_name})
        self._wait_for_join()

    def _wait_for_join(self):
        resp = recv_msg(self.sock)
        if resp:
            action = resp.get("action")
            if action in ["joined_room", "joined_waiting_room"]:
                is_waiting = (action == "joined_waiting_room")
                self.on_join(resp.get("room_name"), is_waiting)
            elif action == "system_message":
                self.status.config(text=resp.get("text", "Error connecting to room."))
                
    def _logout(self):
        self.on_logout()


class DrawCanvas(tk.Frame):
    W, H = 680, 480

    def __init__(self, parent, on_draw, on_clear):
        super().__init__(parent, bg=BG_DARK)
        self.on_draw  = on_draw
        self.on_clear = on_clear
        self.drawing  = False
        self.color    = "#222222"
        self.size     = 4
        self.erasing  = False
        self._last    = None
        self._build()

    def _build(self):
        self.toolbar = tk.Frame(self, bg=BG_MID, pady=6)
        self.toolbar.pack(fill="x")

        self._palette_btns = []
        colors = ["#222222","#e05c7a","#f7a66a","#f7e96a",
                  "#5dca8a","#6ab8f7","#7c6af7","#ffffff",
                  "#a0522d","#f0e68c","#20b2aa","#ff69b4"]
        for c in colors:
            b = tk.Button(self.toolbar, bg=c, width=2, relief="flat",
                          cursor="hand2",
                          command=lambda col=c: self._set_color(col))
            b.pack(side="left", padx=2)

        label(self.toolbar, "  Size:", fg=TEXT_DIM, font=("Segoe UI",9)).pack(side="left")
        self.size_var = tk.IntVar(value=4)
        tk.Scale(self.toolbar, from_=1, to=20, orient="horizontal",
                 variable=self.size_var, bg=BG_MID, fg=TEXT_MAIN,
                 highlightthickness=0, troughcolor=BG_DARK, length=80,
                 command=lambda v: setattr(self, 'size', int(v))).pack(side="left")

        styled_btn(self.toolbar, "🧹 Erase", self._toggle_erase, bg=BG_DARK, font=("Segoe UI",9)).pack(side="left", padx=6)
        styled_btn(self.toolbar, "🗑 Clear", self._clear_all,    bg=DANGER,   font=("Segoe UI",9)).pack(side="left", padx=2)

        tk.Button(self.toolbar, text="🎨", bg=BG_MID, fg=TEXT_MAIN, relief="flat",
                  cursor="hand2", command=self._pick_color,
                  font=("Segoe UI",9)).pack(side="left", padx=4)

        self.canvas = tk.Canvas(self, width=self.W, height=self.H,
                                bg="white", cursor="crosshair",
                                highlightthickness=0)
        self.canvas.pack(padx=4, pady=4)

        self.canvas.bind("<ButtonPress-1>",   self._on_press)
        self.canvas.bind("<B1-Motion>",       self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        self._enabled = True

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        self.canvas.config(cursor="crosshair" if enabled else "arrow")

    def set_toolbar_visible(self, visible: bool):
        if visible:
            self.toolbar.pack(fill="x", before=self.canvas)
        else:
            self.toolbar.pack_forget()

    def _set_color(self, c):
        self.color = c
        self.erasing = False

    def _pick_color(self):
        c = colorchooser.askcolor(color=self.color)[1]
        if c:
            self.color = c
            self.erasing = False

    def _toggle_erase(self):
        self.erasing = not self.erasing

    def _clear_all(self):
        self.canvas.delete("all")
        self.on_clear()

    def _on_press(self, e):
        if not self._enabled:
            return
        self._last = (e.x, e.y)
        self.drawing = True

    def _on_drag(self, e):
        if not self._enabled or not self.drawing or self._last is None:
            return
        x0, y0 = self._last
        x1, y1 = e.x, e.y
        col = "white" if self.erasing else self.color
        sz  = self.size * 3 if self.erasing else self.size
        self.canvas.create_line(x0, y0, x1, y1,
                                fill=col, width=sz,
                                capstyle="round", smooth=True)
        self.on_draw({"x0":x0,"y0":y0,"x1":x1,"y1":y1,
                      "color":col,"size":sz})
        self._last = (x1, y1)

    def _on_release(self, _):
        self.drawing = False
        self._last = None

    def remote_draw(self, data: dict):
        self.canvas.create_line(
            data["x0"], data["y0"], data["x1"], data["y1"],
            fill=data.get("color","#000"), width=data.get("size",4),
            capstyle="round", smooth=True
        )

    def clear(self):
        self.canvas.delete("all")


class ChatPanel(tk.Frame):
    def __init__(self, parent, on_send):
        super().__init__(parent, bg=BG_CARD)
        self.on_send = on_send
        self._build()

    def _build(self):
        label(self, "💬 Chat & Guess", font=FONT_HEAD, fg=ACCENT).pack(pady=(8,4), padx=8, anchor="w")

        self.log = tk.Text(self, bg=BG_MID, fg=TEXT_MAIN, font=FONT_MONO,
                           state="disabled", wrap="word", height=22, width=32,
                           relief="flat", padx=6, pady=4)
        self.log.pack(fill="both", expand=True, padx=8, pady=4)

        self._placeholder = label(self, "", fg=DANGER, font=("Segoe UI",9))
        self._placeholder.pack(padx=8, anchor="w")

        row = tk.Frame(self, bg=BG_CARD)
        row.pack(fill="x", padx=8, pady=(0,8))
        self.entry = styled_entry(row, width=20)
        self.entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.entry.bind("<Return>", lambda e: self._send())
        self._send_btn = styled_btn(row, "Send", self._send, bg=ACCENT)
        self._send_btn.pack(side="left", padx=(4,0))

        self.log.tag_config("system",  foreground=TEXT_DIM)
        self.log.tag_config("correct", foreground=SUCCESS)
        self.log.tag_config("self_msg",foreground=ACCENT2)
        self.log.tag_config("other",   foreground=TEXT_MAIN)
        self.log.tag_config("name",    foreground=ACCENT, font=("Consolas",11,"bold"))

    def set_drawer_mode(self, is_drawer: bool):
        if is_drawer:
            self.entry.config(state="disabled", bg=BG_DARK)
            self._send_btn.config(state="disabled", bg=BG_DARK)
            self._placeholder.config(text="✏️ You are drawing — no chatting!")
        else:
            self.entry.config(state="normal", bg=BG_MID)
            self._send_btn.config(state="normal", bg=ACCENT)
            self._placeholder.config(text="")

    def _send(self):
        text = self.entry.get().strip()
        if text:
            self.on_send(text)
            self.entry.delete(0, "end")

    def append(self, text: str, tag="other"):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n", tag)
        self.log.see("end")
        self.log.config(state="disabled")

    def append_chat(self, username: str, text: str, own: bool = False):
        self.log.config(state="normal")
        self.log.insert("end", f"{username}: ", "name")
        self.log.insert("end", text + "\n", "self_msg" if own else "other")
        self.log.see("end")
        self.log.config(state="disabled")


class PlayerPanel(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_CARD, width=180)
        self._build()
        self._entries: dict[str, tk.Label] = {}

    def _build(self):
        label(self, "👥 Players", font=FONT_HEAD, fg=ACCENT).pack(pady=(8,4), padx=8, anchor="w")
        self.inner = tk.Frame(self, bg=BG_CARD)
        self.inner.pack(fill="both", expand=True, padx=8)

    def update_players(self, rankings: list[dict], drawer: str | None = None):
        for w in self.inner.winfo_children():
            w.destroy()
        self._entries = {}
        for r in rankings:
            name  = r.get("username","?")
            score = r.get("score", 0)
            rank  = r.get("rank",  "?")
            color = ACCENT2 if name == drawer else TEXT_MAIN
            row = tk.Frame(self.inner, bg=BG_MID, pady=4)
            row.pack(fill="x", pady=2)
            label(row, f"#{rank}", fg=TEXT_DIM, font=("Segoe UI",9)).pack(side="left", padx=4)
            label(row, name,  fg=color, font=("Segoe UI",10,"bold")).pack(side="left", padx=2)
            label(row, str(score), fg=SUCCESS, font=("Segoe UI",10)).pack(side="right", padx=6)

    def simple_list(self, players: list[str]):
        for w in self.inner.winfo_children():
            w.destroy()
        for p in players:
            tk.Label(self.inner, text=f"• {p}", bg=BG_CARD, fg=TEXT_MAIN,
                     font=FONT_BODY, anchor="w").pack(fill="x", pady=1)


class InfoBar(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG_MID, height=50)
        self._timer_job = None
        self._remaining = 0
        self._build()

    def _build(self):
        self.round_lbl = label(self, "Round — / —", fg=TEXT_DIM, font=FONT_BODY)
        self.round_lbl.pack(side="left", padx=16)

        self.cat_lbl = label(self, "", fg=ACCENT2, font=("Segoe UI", 12, "bold"))
        self.cat_lbl.pack(side="left", padx=(10, 0))

        self.word_lbl = label(self, "", fg=ACCENT, font=("Segoe UI",16,"bold"))
        self.word_lbl.pack(side="left", expand=True)

        self.timer_lbl = label(self, "⏱ —", fg=ACCENT2, font=("Segoe UI",14,"bold"))
        self.timer_lbl.pack(side="right", padx=16)

        self.drawer_lbl = label(self, "", fg=TEXT_DIM, font=("Segoe UI",10))
        self.drawer_lbl.pack(side="right", padx=8)

    def set_round(self, n: int, total: int):
        self.round_lbl.config(text=f"Round {n}/{total}")

    def set_category(self, cat: str):
        self.cat_lbl.config(text=f"[{cat}]" if cat else "")

    def set_word(self, text: str):
        self.word_lbl.config(text=text)

    def set_drawer(self, name: str):
        self.drawer_lbl.config(text=f"✏️ {name} is drawing")

    def start_timer(self, seconds: int):
        self._remaining = seconds
        self._tick()

    def _tick(self):
        if self._timer_job:
            self.after_cancel(self._timer_job)
        if self._remaining <= 0:
            self.timer_lbl.config(text="⏱ 0", fg=DANGER)
            return
        color = DANGER if self._remaining <= 10 else ACCENT2
        self.timer_lbl.config(text=f"⏱ {self._remaining}", fg=color)
        self._remaining -= 1
        self._timer_job = self.after(1000, self._tick)

    def stop_timer(self):
        if self._timer_job:
            self.after_cancel(self._timer_job)
        self.timer_lbl.config(text="⏱ —", fg=TEXT_DIM)


class VoteDialog(tk.Toplevel):
    def __init__(self, parent, choices: list[str], on_choice, seconds=10):
        super().__init__(parent)
        self.title("Vote for a Category!")
        self.configure(bg=BG_DARK)
        self.resizable(False, False)
        self.grab_set()
        self._choice = None
        self._build(choices, on_choice, seconds)
        self.protocol("WM_DELETE_WINDOW", lambda: None) 

    def _build(self, choices, on_choice, seconds):
        label(self, "🗳️ Vote for a category!", font=FONT_HEAD, fg=ACCENT).pack(pady=16, padx=30)
        self.timer = label(self, f"Voting ends in {seconds}s", fg=TEXT_DIM)
        self.timer.pack()
        remaining = [seconds]

        def tick():
            remaining[0] -= 1
            if remaining[0] <= 0:
                if self._choice is None:
                    self._choice = choices[0]
                    on_choice(choices[0])
                    self.destroy()
                return
            self.timer.config(text=f"Voting ends in {remaining[0]}s")
            self.after(1000, tick)

        self.after(1000, tick)

        for c in choices:
            def pick(cat=c):
                if self._choice is None:
                    self._choice = cat
                    on_choice(cat)
                    self.destroy()
            styled_btn(self, c.upper(), pick, bg=ACCENT,
                       font=("Segoe UI",13,"bold")).pack(fill="x", padx=30, pady=4)

        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-300)//2}+{(sh-250)//2}")


def show_results(parent, title: str, rankings: list[dict], all_time: list[dict] | None = None):
    win = tk.Toplevel(parent)
    win.title(title)
    win.configure(bg=BG_DARK)
    win.grab_set()

    label(win, title, font=FONT_TITLE, fg=ACCENT).pack(pady=16, padx=30)
    medals = ["🥇","🥈","🥉"]
    for r in rankings:
        m = medals[r["rank"]-1] if r["rank"] <= 3 else f'#{r["rank"]}'
        row = tk.Frame(win, bg=BG_MID, pady=6)
        row.pack(fill="x", padx=20, pady=2)
        label(row, f"{m}  {r['username']}", fg=TEXT_MAIN, font=("Segoe UI",12,"bold")).pack(side="left", padx=10)
        label(row, str(r['score']), fg=SUCCESS, font=("Segoe UI",12)).pack(side="right", padx=10)

    if all_time:
        label(win, "🌍 All-Time Top 10", font=FONT_HEAD, fg=ACCENT2).pack(pady=(12,4))
        for r in all_time:
            tk.Label(win, text=f"#{r['rank']}  {r['username']}  —  {r['score']}",
                     bg=BG_DARK, fg=TEXT_DIM, font=FONT_BODY).pack()

    styled_btn(win, "Close", win.destroy, bg=ACCENT).pack(pady=16)
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    win.geometry(f"+{(sw-400)//2}+{(sh-500)//2}")


class GameScreen(tk.Frame):
    def __init__(self, master, sock: socket.socket, username: str, room_name: str, on_leave, is_waiting=False):
        super().__init__(master, bg=BG_DARK)
        self.sock     = sock
        self.username = username
        self.room_name = room_name
        self.on_leave = on_leave
        self.is_waiting = is_waiting
        self.is_drawer = False
        self._running = True  
        self._build()
        self.pack(fill="both", expand=True)
        
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()
        
        send_msg(sock, {"action":"get_players"})

    def _build(self):
        self.info_bar = InfoBar(self)
        self.info_bar.pack(fill="x", side="top")

        mid = tk.Frame(self, bg=BG_DARK)
        mid.pack(fill="both", expand=True)

        self.player_panel = PlayerPanel(mid)
        self.player_panel.pack(side="left", fill="y", padx=(8,0), pady=8)

        self.draw_canvas = DrawCanvas(mid,
            on_draw=self._on_local_draw,
            on_clear=self._on_local_clear)
        self.draw_canvas.set_enabled(False)

        self.chat = ChatPanel(mid, on_send=self._on_chat_send)

        self.waiting_frame = tk.Frame(mid, bg=BG_CARD)
        label(self.waiting_frame, "⏳ WAITING ROOM", font=("Segoe UI", 24, "bold"), fg=ACCENT).pack(pady=(120, 10))
        label(self.waiting_frame, "A round is currently in progress.", fg=TEXT_DIM).pack()
        label(self.waiting_frame, "You will join automatically once the Next Round starts..", fg=TEXT_DIM).pack(pady=(2,0))

        if self.is_waiting:
            self.waiting_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        else:
            self.draw_canvas.pack(side="left", padx=8, pady=8)
            self.chat.pack(side="left", fill="both", expand=True, padx=(0,8), pady=8)

        self.bottom = tk.Frame(self, bg=BG_MID, pady=8)
        self.bottom.pack(fill="x", side="bottom")
        
        self.start_btn = styled_btn(self.bottom, "▶  Start Game", self._start_game,
                                    bg=SUCCESS, font=FONT_HEAD)
        if not self.is_waiting:
            self.start_btn.pack(side="left", padx=16)
        
        self.status_lbl = label(self.bottom, f"Logged in as: {self.username}  |  Room: {self.room_name}",
                                fg=TEXT_DIM, font=("Segoe UI",9))
        self.status_lbl.pack(side="left", padx=(16 if self.is_waiting else 0, 0))

        self.leave_btn = styled_btn(self.bottom, "🚪 Leave Room", self._leave_room, bg=DANGER, font=("Segoe UI", 9))
        self.leave_btn.pack(side="right", padx=16)

    def _on_local_draw(self, data: dict):
        send_msg(self.sock, {"action":"draw","data":data})

    def _on_local_clear(self):
        send_msg(self.sock, {"action":"clear_canvas"})

    def _on_chat_send(self, text: str):
        send_msg(self.sock, {"action":"chat","text":text})

    def _start_game(self):
        send_msg(self.sock, {"action":"start_game"})
        
    def _leave_room(self):
        self._running = False
        send_msg(self.sock, {"action": "leave_room"})

    def _recv_loop(self):
        while self._running:
            msg = recv_msg(self.sock)
            if msg is None:
                if self._running:
                    self.after(0, lambda: messagebox.showerror("Disconnected","Lost connection to server."))
                break
            self.after(0, self._handle, msg)

    def _handle(self, msg: dict):
        if not self.winfo_exists():
            return  
            
        action = msg.get("action")

        if action == "left_room_ack":
            self.on_leave()
            return

        elif action == "waiting_sync":
            self.info_bar.start_timer(msg.get("seconds", 0))
            self.player_panel.update_players(msg.get("rankings", []))
            self.info_bar.set_category(msg.get("category", ""))
            self.info_bar.set_word("Waiting for the next round...")

        elif action == "promoted":
            self.is_waiting = False
            self.waiting_frame.pack_forget()
            self.draw_canvas.pack(side="left", padx=8, pady=8)
            self.chat.pack(side="left", fill="both", expand=True, padx=(0,8), pady=8)
            self.chat.append("✅ You have joined the game!", "system")

        elif action == "player_joined":
            self.player_panel.simple_list(msg.get("players",[]))
            self.chat.append(f"⚡ {msg['username']} joined", "system")

        elif action == "player_left":
            self.chat.append(f"👋 {msg['username']} left", "system")

        elif action == "players":
            self.player_panel.simple_list(msg.get("data",[]))

        elif action == "game_started":
            self.start_btn.pack_forget()
            self.chat.append("🎮 Game started!", "system")
            self.info_bar.set_round(1, msg.get("rounds",3))

        elif action == "vote_category":
            choices = msg.get("choices",[])
            seconds = msg.get("seconds",10)
            self.info_bar.set_word("Voting for Category...")
            VoteDialog(self, choices,
                       on_choice=lambda c: send_msg(self.sock, {"action":"submit_vote","category":c}),
                       seconds=seconds)

        elif action == "new_turn":
            drawer = msg.get("drawer","")
            rnd    = msg.get("round",1)
            total  = msg.get("total_rounds",3)
            rankings = msg.get("rankings", [])
            
            self.info_bar.set_round(rnd, total)
            self.info_bar.set_drawer(drawer)
            self.info_bar.set_category(msg.get("category", ""))
            self.info_bar.set_word("…")
            self.info_bar.stop_timer()
            self.draw_canvas.clear()
            self.is_drawer = (drawer == self.username)
            self.draw_canvas.set_enabled(self.is_drawer)
            self.draw_canvas.set_toolbar_visible(self.is_drawer)
            self.chat.set_drawer_mode(self.is_drawer)
            
            self.player_panel.update_players(rankings, drawer)
            self.chat.append(f"─── Round {rnd}/{total} ·  {drawer} draws ───", "system")

        elif action == "turn_started":
            secs = msg.get("seconds", 80)
            self.info_bar.start_timer(secs)
            if msg.get("is_drawer"):
                word = msg.get("word","")
                self.info_bar.set_word(word)
                self.chat.append(f"✏️  Your word: {word.upper()}", "correct")
            else:
                hint = msg.get("hint","")
                wlen = msg.get("word_length", len(hint.replace(" ","")))
                self.info_bar.set_word(f"{hint}  ({wlen} letters)")

        elif action == "hint_update":
            if not self.is_drawer:
                hint = msg.get("hint","")
                self.info_bar.set_word(hint)
                self.chat.append(f"💡 Hint: {hint}", "system")

        elif action == "draw":
            self.draw_canvas.remote_draw(msg.get("data",{}))

        elif action == "clear_canvas":
            self.draw_canvas.clear()

        elif action == "chat":
            own = msg.get("username") == self.username
            self.chat.append_chat(msg["username"], msg["text"], own=own)

        elif action == "correct_guess":
            who = msg.get("username","")
            pts = msg.get("points",0)
            if who == self.username:
                self.chat.append(f"🎉 You guessed correctly! +{pts} pts", "correct")
            else:
                self.chat.append(f"✅ {who} guessed correctly! (+{pts})", "correct")

        elif action == "turn_ended":
            self.info_bar.stop_timer()
            word = msg.get("word","?")
            self.chat.append(f"⏹ Turn ended. Word was: {word.upper()}", "system")
            rankings = msg.get("rankings",[])
            self.player_panel.update_players(rankings)
            show_results(self, f"Word: {word.upper()}", rankings)

        elif action == "game_over":
            final    = msg.get("final_rankings",[])
            all_time = msg.get("all_time",[])
            self.chat.append("🏁 Game over!", "system")
            show_results(self, "🏆 Game Over – Final Scores", final, all_time)
            
            if self.is_waiting:
                self.waiting_frame.pack_forget()
                self.is_waiting = False
                
            self.start_btn.pack(side="left", padx=16)
            self.info_bar.set_category("")
            self.info_bar.set_word("")
            self.info_bar.stop_timer()
            self.info_bar.set_round(0, 0)
            self.info_bar.drawer_lbl.config(text="")
            self.draw_canvas.set_toolbar_visible(False)
            self.draw_canvas.set_enabled(False)
            self.chat.set_drawer_mode(False)
            
            self.player_panel.simple_list(msg.get("players", []))

        elif action == "system_message":
            text = msg.get('text','')
            if "Error connecting" in text or "Cannot join" in text:
                 messagebox.showwarning("System", text)
            else:
                 self.chat.append(f"ℹ️  {text}", "system")

        elif action == "leaderboard":
            data = msg.get("data",[])
            show_results(self, "🌍 All-Time Leaderboard", data)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("🎨 Drawtic.io  —  Draw & Guess")
        self.configure(bg=BG_DARK)
        self.geometry("1080x680")
        self.minsize(900, 620)
        self._current = None
        self.sock = None
        self.username = None
        self._show_auth()

    def _show_auth(self):
        if self._current:
            self._current.destroy()
        self._current = AuthScreen(self, self._on_auth)

    def _on_auth(self, sock: socket.socket, username: str, message: str):
        self.sock = sock
        self.username = username
        self._show_lobby()

    def _show_lobby(self):
        if self._current:
            self._current.destroy()
        self._current = RoomScreen(self, self.sock, self.username, self._on_room_join, self._on_logout)
        self.title(f"🎨 Drawtic.io  —  {self.username} (Lobby)")

    def _on_room_join(self, room_name: str, is_waiting: bool = False):
        if self._current:
            self._current.destroy()
        self._current = GameScreen(self, self.sock, self.username, room_name, self._show_lobby, is_waiting)
        mode = "Waiting Room" if is_waiting else "Room"
        self.title(f"🎨 Drawtic.io  —  {self.username}  |  {mode}: {room_name}")

    def _on_logout(self):
        if self.sock:
            send_msg(self.sock, {"action": "logout"})
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        self.username = None
        self._show_auth()

if __name__ == "__main__":
    app = App()
    app.mainloop()
