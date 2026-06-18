import socket
import threading
import json
import random
import time
import hashlib
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SERVER] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Word Bank
WORD_BANK = [
    "apple", "banana", "car", "dog", "elephant", "flower", "guitar",
    "house", "island", "jungle", "kite", "lion", "moon", "night",
    "ocean", "piano", "queen", "rainbow", "star", "tree", "umbrella",
    "violin", "whale", "xylophone", "yacht", "zebra", "airplane",
    "balloon", "castle", "diamond", "eagle", "forest", "giraffe",
    "hammer", "igloo", "jacket", "kettle", "ladder", "mountain",
    "noodle", "orange", "penguin", "quilt", "rocket", "sunflower",
    "tiger", "unicorn", "volcano", "waterfall", "fox", "yarn",
    "pizza", "burger", "sandwich", "coffee", "book", "phone",
    "computer", "bicycle", "bridge", "butterfly", "camera", "candle",
    "clock", "cloud", "crown", "desert", "dragon", "dream",
    "earth", "fire", "ghost", "glasses", "globe", "gold",
    "heart", "helmet", "honey", "horse", "lantern", "leaf",
    "lighthouse", "magic", "map", "mask", "medal", "mirror",
    "mushroom", "nest", "newspaper", "ninja", "nurse", "painting",
    "parrot", "planet", "robot", "rose", "sail", "ship",
    "shoes", "snake", "snowflake", "spider", "suitcase", "sword",
    "temple", "tent", "thunder", "torch", "tower", "trophy",
    "turtle", "village", "wand", "watch", "window", "wolf"
]


# Utility – framed JSON over TCP
def send_msg(sock: socket.socket, data: dict) -> bool:
    """Send a length-prefixed JSON message."""
    try:
        payload = json.dumps(data).encode('utf-8')
        length = len(payload).to_bytes(4, 'big')
        sock.sendall(length + payload)
        return True
    except Exception:
        return False


def recv_msg(sock: socket.socket) -> dict | None:
    """Receive a length-prefixed JSON message."""
    try:
        raw_len = _recv_exact(sock, 4)
        if raw_len is None:
            return None
        msg_len = int.from_bytes(raw_len, 'big')
        raw = _recv_exact(sock, msg_len)
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


# User Manager
class UserManager:
    def __init__(self):
        self._users: dict[str, str] = {}   
        self._lock = threading.Lock()

    def _hash(self, pw: str) -> str:
        return hashlib.sha256(pw.encode()).hexdigest()

    def register(self, username: str, password: str) -> tuple[bool, str]:
        with self._lock:
            if not username or not password:
                return False, "Username and password required."
            if len(username) < 3:
                return False, "Username must be at least 3 characters."
            if username in self._users:
                return False, "Username already taken."
            self._users[username] = self._hash(password)
            logger.info(f"Registered user: {username}")
            return True, "Registration successful."

    def login(self, username: str, password: str) -> tuple[bool, str]:
        with self._lock:
            if username not in self._users:
                return False, "User not found."
            if self._users[username] != self._hash(password):
                return False, "Wrong password."
            return True, "Login successful."


# Leaderboard
class Leaderboard:
    def __init__(self):
        self._scores: dict[str, int] = {}
        self._lock = threading.Lock()

    def add_score(self, username: str, points: int):
        with self._lock:
            self._scores[username] = self._scores.get(username, 0) + points

    def reset_game_scores(self, players: list[str]):
        with self._lock:
            for p in players:
                self._scores.setdefault(p, 0)

    def get_rankings(self, players: list[str]) -> list[dict]:
        with self._lock:
            ranked = sorted(
                [{"username": p, "score": self._scores.get(p, 0)} for p in players],
                key=lambda x: x["score"],
                reverse=True
            )
            for i, r in enumerate(ranked):
                r["rank"] = i + 1
            return ranked

    def get_all_time(self) -> list[dict]:
        with self._lock:
            ranked = sorted(
                [{"username": u, "score": s} for u, s in self._scores.items()],
                key=lambda x: x["score"],
                reverse=True
            )
            for i, r in enumerate(ranked):
                r["rank"] = i + 1
            return ranked[:10]


# Game State
class GameState:
    LOBBY   = "lobby"
    PLAYING = "playing"
    RESULTS = "results"

    ROUND_DURATION = 80 
    ROUNDS_PER_GAME = 3
    WORD_CHOICES = 3

    def __init__(self):
        self.status = self.LOBBY
        self.players: list[str] = []         
        self.current_drawer: str | None = None
        self.current_word: str | None = None
        self.current_word_hint: str | None = None
        self.round_number = 0
        self.turn_index = 0
        self.turn_start: float | None = None
        self.guessed: set[str] = set()       
        self.word_choices: list[str] = []
        self._lock = threading.Lock()

    def _make_hint(self, word: str) -> str:
        return ' '.join(['_' if c != ' ' else ' ' for c in word])

    def pick_word_choices(self) -> list[str]:
        return random.sample(WORD_BANK, self.WORD_CHOICES)

    def start_game(self, players: list[str]):
        with self._lock:
            self.players = players[:]
            random.shuffle(self.players)
            self.status = self.PLAYING
            self.round_number = 1
            self.turn_index = 0
            self.current_drawer = self.players[0]
            self.guessed = set()
            self.turn_start = None
            self.current_word = None
            self.current_word_hint = None

    def set_word(self, word: str):
        with self._lock:
            self.current_word = word
            self.current_word_hint = self._make_hint(word)
            self.turn_start = time.time()
            self.guessed = set()

    def reveal_hint_letter(self):
        with self._lock:
            if not self.current_word or not self.current_word_hint:
                return
            hint = list(self.current_word_hint)
            hidden = [i for i, c in enumerate(hint) if c == '_']
            if not hidden:
                return
            idx = random.choice(hidden)
            hint[idx] = self.current_word[idx]
            self.current_word_hint = ''.join(hint)

    def time_remaining(self) -> int:
        if self.turn_start is None:
            return self.ROUND_DURATION
        elapsed = time.time() - self.turn_start
        return max(0, int(self.ROUND_DURATION - elapsed))

    def score_for_guess(self) -> int:
        time_left = self.time_remaining()
        return max(50, 100 + int(time_left * 1.5))

    def drawer_bonus(self, guessers: int) -> int:
        return guessers * 30

    def next_turn(self) -> bool:
        with self._lock:
            self.turn_index += 1
            self.guessed = set()
            self.current_word = None
            self.current_word_hint = None
            self.turn_start = None
            if self.turn_index >= len(self.players):
                self.turn_index = 0
                self.round_number += 1
                if self.round_number > self.ROUNDS_PER_GAME:
                    self.status = self.RESULTS
                    return False
            self.current_drawer = self.players[self.turn_index]
            return True


# Server
class SkribblServer:
    MIN_PLAYERS = 2
    HOST = '0.0.0.0'
    PORT = 9999

    def __init__(self):
        self.user_mgr  = UserManager()
        self.leaderboard = Leaderboard()
        self.game = GameState()

        self.clients: dict[str, socket.socket] = {}
        self.client_lock = threading.Lock()

        self.authenticated: set[str] = set()

        self._server_sock: socket.socket | None = None
        self._turn_timer: threading.Timer | None = None
        self._hint_thread: threading.Thread | None = None

    def start(self):
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.HOST, self.PORT))
        self._server_sock.listen(16)
        logger.info(f"Server listening on {self.HOST}:{self.PORT}")
        try:
            while True:
                conn, addr = self._server_sock.accept()
                logger.info(f"New connection from {addr}")
                t = threading.Thread(target=self._handle_client, args=(conn,), daemon=True)
                t.start()
        except KeyboardInterrupt:
            logger.info("Server shutting down.")
        finally:
            self._server_sock.close()

    def broadcast(self, data: dict, exclude: str | None = None):
        with self.client_lock:
            dead = []
            for uname, sock in self.clients.items():
                if uname == exclude:
                    continue
                if not send_msg(sock, data):
                    dead.append(uname)
            for uname in dead:
                self._remove_client(uname)

    def send_to(self, username: str, data: dict):
        with self.client_lock:
            sock = self.clients.get(username)
        if sock:
            send_msg(sock, data)

    # client handler
    def _handle_client(self, conn: socket.socket):
        username = None
        try:
            while True:
                msg = recv_msg(conn)
                if msg is None:
                    break
                action = msg.get("action")

                # Auth phase
                if action == "register":
                    ok, text = self.user_mgr.register(msg.get("username",""), msg.get("password",""))
                    send_msg(conn, {"action":"register_result","ok":ok,"message":text})

                elif action == "login":
                    uname = msg.get("username","")
                    ok, text = self.user_mgr.login(uname, msg.get("password",""))
                    if ok:
                        with self.client_lock:
                            if uname in self.clients:
                                send_msg(conn, {"action":"login_result","ok":False,"message":"Already logged in from another session."})
                                continue
                            self.clients[uname] = conn
                            self.authenticated.add(uname)
                        username = uname
                        send_msg(conn, {"action":"login_result","ok":True,"message":text})
                        self._on_player_joined(uname)
                    else:
                        send_msg(conn, {"action":"login_result","ok":False,"message":text})

                # Authenticated actions
                elif action == "chat":
                    if username:
                        self._handle_chat(username, msg.get("text",""))

                elif action == "draw":
                    if username and username == self.game.current_drawer:
                        self.broadcast({
                            "action":"draw",
                            "data": msg.get("data",{})
                        }, exclude=username)

                elif action == "clear_canvas":
                    if username and username == self.game.current_drawer:
                        self.broadcast({"action":"clear_canvas"}, exclude=username)

                elif action == "choose_word":
                    if username and username == self.game.current_drawer:
                        word = msg.get("word","")
                        if word in self.game.word_choices:
                            self._start_turn_with_word(word)

                elif action == "start_game":
                    if username:
                        self._try_start_game(username)

                elif action == "get_leaderboard":
                    data = self.leaderboard.get_all_time()
                    send_msg(conn, {"action":"leaderboard","data":data})

                elif action == "get_players":
                    with self.client_lock:
                        players = list(self.clients.keys())
                    send_msg(conn, {"action":"players","data":players})

        except Exception as e:
            logger.error(f"Client handler error ({username}): {e}")
        finally:
            if username:
                self._remove_client(username)
                self.broadcast({"action":"player_left","username":username})
                logger.info(f"Player disconnected: {username}")
            conn.close()

    def _remove_client(self, username: str):
        with self.client_lock:
            self.clients.pop(username, None)
            self.authenticated.discard(username)

    # Game flow
    def _on_player_joined(self, username: str):
        with self.client_lock:
            players = list(self.clients.keys())
        self.broadcast({
            "action": "player_joined",
            "username": username,
            "players": players,
            "game_status": self.game.status
        })
        logger.info(f"{username} joined. Players: {players}")

    def _try_start_game(self, requester: str):
        with self.client_lock:
            players = list(self.clients.keys())
        if len(players) < self.MIN_PLAYERS:
            self.send_to(requester, {
                "action":"system_message",
                "text": f"Need at least {self.MIN_PLAYERS} players to start."
            })
            return
        if self.game.status != GameState.LOBBY:
            self.send_to(requester, {"action":"system_message","text":"Game already in progress."})
            return
        self.leaderboard.reset_game_scores(players)
        self.game.start_game(players)
        self.broadcast({
            "action":"game_started",
            "players": players,
            "rounds": GameState.ROUNDS_PER_GAME
        })
        self._begin_drawer_turn()

    def _begin_drawer_turn(self):
        drawer = self.game.current_drawer
        choices = self.game.pick_word_choices()
        self.game.word_choices = choices

        self.broadcast({
            "action":"new_turn",
            "drawer": drawer,
            "round": self.game.round_number,
            "total_rounds": GameState.ROUNDS_PER_GAME
        })
        self.send_to(drawer, {
            "action":"choose_word",
            "choices": choices,
            "seconds": 15
        })
        t = threading.Timer(15.0, self._auto_pick_word)
        t.daemon = True
        t.start()

    def _auto_pick_word(self):
        if self.game.current_word is None and self.game.word_choices:
            word = random.choice(self.game.word_choices)
            self._start_turn_with_word(word)

    def _start_turn_with_word(self, word: str):
        self.game.set_word(word)
        hint = self.game.current_word_hint
        word_len = len(word)

        self.send_to(self.game.current_drawer, {
            "action":"turn_started",
            "word": word,
            "hint": hint,
            "seconds": GameState.ROUND_DURATION,
            "is_drawer": True
        })
        # Tell others only hint + length
        with self.client_lock:
            players = list(self.clients.keys())
        for p in players:
            if p != self.game.current_drawer:
                self.send_to(p, {
                    "action":"turn_started",
                    "hint": hint,
                    "word_length": word_len,
                    "seconds": GameState.ROUND_DURATION,
                    "is_drawer": False
                })

        if self._turn_timer:
            self._turn_timer.cancel()
        self._turn_timer = threading.Timer(GameState.ROUND_DURATION, self._on_turn_timeout)
        self._turn_timer.daemon = True
        self._turn_timer.start()

        # Hint reveal thread
        self._hint_thread = threading.Thread(target=self._hint_reveal_loop, daemon=True)
        self._hint_thread.start()

    def _hint_reveal_loop(self):
        word = self.game.current_word
        if not word:
            return
        reveal_times = [GameState.ROUND_DURATION // 3, (GameState.ROUND_DURATION * 2) // 3]
        for delay in reveal_times:
            time.sleep(delay)
            if self.game.current_word != word:
                return
            self.game.reveal_hint_letter()
            hint = self.game.current_word_hint
            if hint:
                self.broadcast({
                    "action":"hint_update",
                    "hint": hint
                })

    def _handle_chat(self, username: str, text: str):
        if not text.strip():
            return
        word = self.game.current_word
        if (self.game.status == GameState.PLAYING
                and word
                and username != self.game.current_drawer
                and username not in self.game.guessed):
            if text.strip().lower() == word.lower():
                self._on_correct_guess(username)
                return

        # Normal chat
        self.broadcast({
            "action":"chat",
            "username": username,
            "text": text,
            "timestamp": datetime.now().strftime("%H:%M")
        })

    def _on_correct_guess(self, username: str):
        pts = self.game.score_for_guess()
        self.game.guessed.add(username)
        self.leaderboard.add_score(username, pts)

        # Announce (without revealing word)
        self.broadcast({
            "action":"correct_guess",
            "username": username,
            "points": pts
        })

        # Check if everyone guessed
        with self.client_lock:
            active = set(self.clients.keys())
        non_drawers = active - {self.game.current_drawer}
        if non_drawers and non_drawers <= self.game.guessed:
            self._end_turn(all_guessed=True)

    def _on_turn_timeout(self):
        self._end_turn(all_guessed=False)

    def _end_turn(self, all_guessed: bool):
        if self._turn_timer:
            self._turn_timer.cancel()
            self._turn_timer = None

        # Drawer bonus
        n_guessed = len(self.game.guessed)
        if n_guessed > 0:
            bonus = self.game.drawer_bonus(n_guessed)
            self.leaderboard.add_score(self.game.current_drawer, bonus)

        with self.client_lock:
            players = list(self.clients.keys())
        rankings = self.leaderboard.get_rankings(players)

        self.broadcast({
            "action":"turn_ended",
            "word": self.game.current_word,
            "all_guessed": all_guessed,
            "rankings": rankings
        })

        time.sleep(4)

        has_next = self.game.next_turn()
        if has_next:
            self.broadcast({"action":"clear_canvas"})
            self._begin_drawer_turn()
        else:
            self._end_game()

    def _end_game(self):
        with self.client_lock:
            players = list(self.clients.keys())
        final = self.leaderboard.get_rankings(players)
        all_time = self.leaderboard.get_all_time()
        self.broadcast({
            "action":"game_over",
            "final_rankings": final,
            "all_time": all_time
        })
        # Reset to lobby
        self.game.status = GameState.LOBBY
        logger.info("Game over. Back to lobby.")


if __name__ == "__main__":
    server = SkribblServer()
    server.start()
