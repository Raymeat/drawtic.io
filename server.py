import socket
import threading
import json
import random
import time
import hashlib
import logging
import os
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [SERVER] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

def get_real_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "127.0.0.1"

# --- JSON Dictionary Management ---
DEFAULT_WORDS = {
    "Animals": ["dog", "cat", "elephant", "lion", "tiger", "zebra", "monkey", "giraffe", "penguin", "kangaroo"],
    "Food": ["pizza", "burger", "apple", "banana", "coffee", "sandwich", "noodle", "orange", "pancake"],
    "Objects": ["car", "guitar", "house", "piano", "umbrella", "helmet", "camera", "telephone", "telescope"],
    "Nature": ["mountain", "river", "forest", "volcano", "ocean", "desert", "rainbow", "tornado", "waterfall"],
    "Professions": ["doctor", "teacher", "police", "artist", "farmer", "pilot", "nurse", "scientist", "chef"]
}

def load_words():
    filepath = "words.json"
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and len(data) > 0:
                    logger.info(f"Loaded words from {filepath} successfully.")
                    return data
        except Exception as e:
            logger.error(f"Failed to load words.json: {e}")
            
    # Fallback: create the file with default words if missing
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_WORDS, f, indent=4)
        logger.info(f"Created default {filepath}")
    except Exception:
        pass
    return DEFAULT_WORDS

WORD_DATA = load_words()


def send_msg(sock: socket.socket, data: dict) -> bool:
    try:
        payload = json.dumps(data).encode('utf-8')
        length = len(payload).to_bytes(4, 'big')
        sock.sendall(length + payload)
        return True
    except Exception:
        return False

def recv_msg(sock: socket.socket) -> dict | None:
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

class UserManager:
    def __init__(self, filename="user.txt"):
        self.filename = filename
        self._users: dict[str, str] = {}   
        self._lock = threading.Lock()
        self._load_users()

    def _load_users(self):
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and ':' in line:
                            uname, pwd_hash = line.split(':', 1)
                            self._users[uname] = pwd_hash
                logger.info(f"Loaded {len(self._users)} users from {self.filename}")
            except Exception as e:
                logger.error(f"Failed to load users: {e}")
        else:
            logger.info(f"No existing user file found at {self.filename}. A new one will be created.")

    def _save_users(self):
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                for uname, pwd_hash in self._users.items():
                    f.write(f"{uname}:{pwd_hash}\n")
        except Exception as e:
            logger.error(f"Failed to save users: {e}")

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
            self._save_users()
            logger.info(f"Registered user: {username}")
            return True, "Registration successful."

    def login(self, username: str, password: str) -> tuple[bool, str]:
        with self._lock:
            if username not in self._users:
                return False, "User not found."
            if self._users[username] != self._hash(password):
                return False, "Wrong password."
            return True, "Login successful."

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

class GameState:
    LOBBY   = "lobby"
    PLAYING = "playing"
    RESULTS = "results"

    ROUND_DURATION = 80 
    ROUNDS_PER_GAME = 3

    def __init__(self, room_name: str):
        self.room_name = room_name
        self.status = self.LOBBY
        self.players: list[str] = []         
        self.waiting_players: list[str] = [] 
        self.current_drawer: str | None = None
        self.current_word: str | None = None
        self.current_word_hint: str | None = None
        self.round_number = 0
        self.turn_index = 0
        self.turn_start: float | None = None
        self.guessed: set[str] = set()       
        self.leaderboard = Leaderboard() 
        
        # --- NEW: Round Category & Word memory ---
        self.word_data = WORD_DATA
        self.categories = list(self.word_data.keys())
        self.current_category: str = ""
        self.category_choices: list[str] = []
        self.recent_words: list[str] = []
        self.voting_state: dict[str, str] = {}
        self._voting_ended = False
        
        self.turn_timer: threading.Timer | None = None
        self.hint_thread: threading.Thread | None = None
        self.pick_timer: threading.Timer | None = None  
        self._ending_turn: bool = False                 
        self._lock = threading.Lock()

    def _make_hint(self, word: str) -> str:
        return ''.join(['_' if c != ' ' else ' ' for c in word])

    def pick_category_choices(self) -> list[str]:
        num_choices = min(3, len(self.categories))
        return random.sample(self.categories, num_choices)

    def pick_word_from_category(self, category: str) -> str:
        pool = self.word_data.get(category, [])
        if not pool:
            pool = ["error"]
            
        valid = [w for w in pool if w not in self.recent_words]
        if not valid:
            valid = pool # Reset constraints if every word in category is exhausted
            
        word = random.choice(valid)
        self.recent_words.append(word)
        if len(self.recent_words) > 3:
            self.recent_words.pop(0) 
        return word

    def start_game(self):
        with self._lock:
            random.shuffle(self.players)
            self.status = self.PLAYING
            self.round_number = 1
            self.turn_index = 0
            self.current_drawer = self.players[0]
            self.guessed = set()
            self.turn_start = None
            self.current_word = None
            self.current_word_hint = None
            self.recent_words.clear()

    def set_word(self, word: str) -> bool:
        with self._lock:
            if self.current_word is not None:
                return False
            self.current_word = word
            self.current_word_hint = self._make_hint(word)
            self.turn_start = time.time()
            self.guessed = set()
            return True

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

            if len(self.players) < 2:
                self.status = self.RESULTS
                return False

            if self.turn_index >= len(self.players):
                self.turn_index = 0
                self.round_number += 1
                if self.round_number > self.ROUNDS_PER_GAME:
                    self.status = self.RESULTS
                    return False
            self.current_drawer = self.players[self.turn_index]
            return True


class DrawticServer:
    MIN_PLAYERS = 2
    HOST = '0.0.0.0'
    PORT = 9999
    DISCOVERY_PORT = 9998

    def __init__(self):
        self.user_mgr  = UserManager()
        self.global_leaderboard = Leaderboard() 
        
        self.rooms: dict[str, GameState] = {}       
        self.player_rooms: dict[str, str] = {}      
        
        self.clients: dict[str, socket.socket] = {} 
        self.client_lock = threading.Lock()
        self.authenticated: set[str] = set()
        self._server_sock: socket.socket | None = None
        self.real_ip = get_real_ip()

    def _start_discovery_service(self):
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_sock.bind(('0.0.0.0', self.DISCOVERY_PORT))
        
        while True:
            try:
                data, addr = udp_sock.recvfrom(1024)
                if data == b"DISCOVER_SKRIBBL_SERVER":
                    payload = f"SKRIBBL_SERVER_HERE:{self.real_ip}".encode('utf-8')
                    udp_sock.sendto(payload, addr)
            except Exception as e:
                logger.error(f"Discovery error: {e}")

    def start(self):
        discovery_thread = threading.Thread(target=self._start_discovery_service, daemon=True)
        discovery_thread.start()

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.HOST, self.PORT))
        self._server_sock.listen(16)
        
        logger.info("=========================================================")
        logger.info(f" SERVER STARTED SUCCESSFULLY! ")
        logger.info(f" -> Auto-Detect should find IP: {self.real_ip}")
        logger.info("=========================================================")
        
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

    def broadcast_to_room(self, room_name: str, data: dict, exclude: str | None = None, include_waiting=False):
        if room_name not in self.rooms:
            return
            
        with self.client_lock:
            dead = []
            game = self.rooms[room_name]
            targets = game.players[:]
            if include_waiting:
                targets.extend(game.waiting_players)
            
            for uname in targets:
                if uname == exclude:
                    continue
                sock = self.clients.get(uname)
                if sock:
                    if not send_msg(sock, data):
                        dead.append(uname)
            for uname in dead:
                self._remove_client(uname)

    def send_to(self, username: str, data: dict):
        with self.client_lock:
            sock = self.clients.get(username)
        if sock:
            send_msg(sock, data)

    def _handle_client(self, conn: socket.socket):
        username = None
        try:
            while True:
                msg = recv_msg(conn)
                if msg is None:
                    break
                action = msg.get("action")

                if action == "logout":
                    break 

                elif action == "register":
                    ok, text = self.user_mgr.register(msg.get("username",""), msg.get("password",""))
                    send_msg(conn, {"action":"register_result","ok":ok,"message":text})

                elif action == "login":
                    uname = msg.get("username","")
                    ok, text = self.user_mgr.login(uname, msg.get("password",""))
                    if ok:
                        with self.client_lock:
                            if uname in self.clients:
                                send_msg(conn, {"action":"login_result","ok":False,"message":"Already logged in."})
                                continue
                            self.clients[uname] = conn
                            self.authenticated.add(uname)
                        username = uname
                        send_msg(conn, {"action":"login_result","ok":True,"message":text})
                    else:
                        send_msg(conn, {"action":"login_result","ok":False,"message":text})

                elif action == "get_rooms":
                    if username:
                        room_list = list(self.rooms.keys())
                        send_msg(conn, {"action": "room_list", "rooms": room_list})
                        
                elif action == "create_room":
                    if username:
                        room_name = msg.get("room_name", f"Room_{random.randint(1000,9999)}")
                        if room_name not in self.rooms:
                            self.rooms[room_name] = GameState(room_name)
                            logger.info(f"Room created: {room_name}")
                        self._join_room(username, room_name)
                        
                elif action == "join_room":
                    if username:
                        room_name = msg.get("room_name", "")
                        if room_name in self.rooms:
                            self._join_room(username, room_name)
                        else:
                            send_msg(conn, {"action":"system_message","text":"Room does not exist."})
                            
                elif action == "leave_room":
                    if username:
                        self._leave_current_room(username)
                        send_msg(conn, {"action": "left_room_ack"})

                else:
                    if not username:
                        continue
                    
                    room_name = self.player_rooms.get(username)
                    if not room_name or room_name not in self.rooms:
                        continue
                        
                    game = self.rooms[room_name]

                    if action == "chat":
                        self._handle_chat(username, room_name, game, msg.get("text",""))

                    elif action == "draw":
                        if username == game.current_drawer:
                            self.broadcast_to_room(room_name, {
                                "action":"draw",
                                "data": msg.get("data",{})
                            }, exclude=username)

                    elif action == "clear_canvas":
                        if username == game.current_drawer:
                            self.broadcast_to_room(room_name, {"action":"clear_canvas"}, exclude=username)

                    elif action == "submit_vote":
                        category = msg.get("category", "")
                        if username in game.players and category in game.category_choices:
                            trigger_end = False
                            with game._lock:
                                if not getattr(game, '_voting_ended', False) and username not in game.voting_state:
                                    game.voting_state[username] = category
                                    if len(game.voting_state) >= len(game.players):
                                        trigger_end = True
                            if trigger_end:
                                self._end_voting(room_name, game)

                    elif action == "start_game":
                        self._try_start_game(username, room_name, game)

                    elif action == "get_leaderboard":
                        data = self.global_leaderboard.get_all_time()
                        send_msg(conn, {"action":"leaderboard","data":data})

                    elif action == "get_players":
                        send_msg(conn, {"action":"players","data":game.players})

        except Exception as e:
            logger.error(f"Client handler error ({username}): {e}")
        finally:
            if username:
                self._leave_current_room(username)
                self._remove_client(username)
                logger.info(f"Player disconnected completely: {username}")
            conn.close()

    def _remove_client(self, username: str):
        with self.client_lock:
            self.clients.pop(username, None)
            self.authenticated.discard(username)

    def _join_room(self, username: str, room_name: str):
        self._leave_current_room(username) 
        
        game = self.rooms[room_name]
        self.player_rooms[username] = room_name

        if game.status == GameState.PLAYING:
            game.waiting_players.append(username)
            self.send_to(username, {"action": "joined_waiting_room", "room_name": room_name})
            
            rankings = game.leaderboard.get_rankings(game.players)
            self.send_to(username, {
                "action": "waiting_sync",
                "seconds": game.time_remaining(),
                "rankings": rankings,
                "category": game.current_category
            })
            logger.info(f"{username} joined {room_name} (WAITING ROOM).")
        else:
            game.players.append(username)
            self.send_to(username, {"action": "joined_room", "room_name": room_name})
            self.broadcast_to_room(room_name, {
                "action": "player_joined",
                "username": username,
                "players": game.players,
                "game_status": game.status
            })
            logger.info(f"{username} joined {room_name}. Players: {game.players}")
        
    def _leave_current_room(self, username: str):
        room_name = self.player_rooms.pop(username, None)
        if room_name and room_name in self.rooms:
            game = self.rooms[room_name]
            was_drawer = False
            
            with game._lock:
                if username in game.players:
                    idx = game.players.index(username)
                    game.players.remove(username)
                    if game.status == GameState.PLAYING:
                        if idx <= game.turn_index:
                            game.turn_index -= 1
                        if username == game.current_drawer:
                            was_drawer = True
                elif username in game.waiting_players:
                    game.waiting_players.remove(username)
                    
            self.broadcast_to_room(room_name, {
                "action": "player_left",
                "username": username
            }, include_waiting=True)

            if was_drawer:
                threading.Thread(target=self._end_turn, args=(room_name, game, False), daemon=True).start()
                
            if len(game.players) == 0 and len(game.waiting_players) == 0:
                self.rooms.pop(room_name, None)
                logger.info(f"Room {room_name} destroyed (empty).")

    def _try_start_game(self, requester: str, room_name: str, game: GameState):
        if len(game.players) < self.MIN_PLAYERS:
            self.send_to(requester, {
                "action":"system_message",
                "text": f"Need at least {self.MIN_PLAYERS} players to start."
            })
            return
        if game.status != GameState.LOBBY:
            self.send_to(requester, {"action":"system_message","text":"Game already in progress."})
            return
            
        game.leaderboard.reset_game_scores(game.players)
        game.start_game()
        
        self.broadcast_to_room(room_name, {
            "action":"game_started",
            "players": game.players,
            "rounds": game.ROUNDS_PER_GAME
        })
        self._begin_round_vote(room_name, game)

    def _begin_round_vote(self, room_name: str, game: GameState):
        choices = game.pick_category_choices()
        game.category_choices = choices
        game.voting_state = {}
        
        with game._lock:
            game._ending_turn = False
            game._voting_ended = False

        self.broadcast_to_room(room_name, {
            "action": "vote_category",
            "choices": choices,
            "seconds": 10
        }, include_waiting=False)
        
        game.pick_timer = threading.Timer(10.0, lambda: self._end_voting(room_name, game))
        game.pick_timer.daemon = True
        game.pick_timer.start()

    def _end_voting(self, room_name: str, game: GameState):
        with game._lock:
            if getattr(game, '_voting_ended', False):
                return
            game._voting_ended = True

            if getattr(game, 'pick_timer', None):
                game.pick_timer.cancel()
                game.pick_timer = None
                
            vote_counts = {cat: 0 for cat in game.category_choices}
            for user, cat in game.voting_state.items():
                if cat in vote_counts:
                    vote_counts[cat] += 1
                    
            max_votes = max(vote_counts.values()) if vote_counts else 0
            tied = [cat for cat, count in vote_counts.items() if count == max_votes]
            
            winning_cat = random.choice(tied) if tied else random.choice(game.category_choices)
            game.current_category = winning_cat

        self.broadcast_to_room(room_name, {
            "action": "system_message",
            "text": f"🗳️ Category '{winning_cat}' won the vote!"
        }, include_waiting=True)

        self._begin_drawer_turn(room_name, game)

    def _begin_drawer_turn(self, room_name: str, game: GameState):
        drawer = game.current_drawer
        chosen_word = game.pick_word_from_category(game.current_category)
        
        rankings = game.leaderboard.get_rankings(game.players)

        self.broadcast_to_room(room_name, {
            "action":"new_turn",
            "drawer": drawer,
            "round": game.round_number,
            "total_rounds": game.ROUNDS_PER_GAME,
            "rankings": rankings,
            "category": game.current_category
        }, include_waiting=True)

        self._start_turn_with_word(room_name, game, chosen_word)

    def _start_turn_with_word(self, room_name: str, game: GameState, word: str):
        if not game.set_word(word):
            return

        hint = game.current_word_hint
        word_len = len(word.replace(" ", ""))

        self.send_to(game.current_drawer, {
            "action":"turn_started",
            "word": word,
            "hint": ' '.join(hint),
            "seconds": game.ROUND_DURATION,
            "is_drawer": True
        })
        
        for p in game.players:
            if p != game.current_drawer:
                self.send_to(p, {
                    "action":"turn_started",
                    "hint": ' '.join(hint),
                    "word_length": word_len,
                    "seconds": game.ROUND_DURATION,
                    "is_drawer": False
                })
            
        game.turn_timer = threading.Timer(game.ROUND_DURATION, lambda: self._on_turn_timeout(room_name, game))
        game.turn_timer.daemon = True
        game.turn_timer.start()

        game.hint_thread = threading.Thread(target=self._hint_reveal_loop, args=(room_name, game), daemon=True)
        game.hint_thread.start()

    def _hint_reveal_loop(self, room_name: str, game: GameState):
        word = game.current_word
        if not word:
            return
        reveal_times = [game.ROUND_DURATION // 3, (game.ROUND_DURATION * 2) // 3]
        for delay in reveal_times:
            time.sleep(delay)
            if game.current_word != word:
                return
            game.reveal_hint_letter()
            hint = game.current_word_hint
            if hint:
                self.broadcast_to_room(room_name, {
                    "action":"hint_update",
                    "hint": ' '.join(hint)
                })

    def _handle_chat(self, username: str, room_name: str, game: GameState, text: str):
        if not text.strip():
            return
        word = game.current_word
        if (game.status == GameState.PLAYING
                and word
                and username != game.current_drawer
                and username not in game.guessed):
            if text.strip().lower() == word.lower():
                self._on_correct_guess(username, room_name, game)
                return

        self.broadcast_to_room(room_name, {
            "action":"chat",
            "username": username,
            "text": text,
            "timestamp": datetime.now().strftime("%H:%M")
        })

    def _on_correct_guess(self, username: str, room_name: str, game: GameState):
        pts = game.score_for_guess()
        game.guessed.add(username)
        game.leaderboard.add_score(username, pts)
        self.global_leaderboard.add_score(username, pts) 

        self.broadcast_to_room(room_name, {
            "action":"correct_guess",
            "username": username,
            "points": pts
        })

        active_in_room = set(game.players)
        non_drawers = active_in_room - {game.current_drawer}
        if non_drawers and non_drawers <= game.guessed:
            self._end_turn(room_name, game, all_guessed=True)

    def _on_turn_timeout(self, room_name: str, game: GameState):
        self._end_turn(room_name, game, all_guessed=False)

    def _end_turn(self, room_name: str, game: GameState, all_guessed: bool):
        with game._lock:
            if getattr(game, '_ending_turn', False):
                return
            game._ending_turn = True

            if getattr(game, 'turn_timer', None):
                game.turn_timer.cancel()
                game.turn_timer = None
            if getattr(game, 'pick_timer', None):
                game.pick_timer.cancel()
                game.pick_timer = None

        n_guessed = len(game.guessed)
        if n_guessed > 0:
            bonus = game.drawer_bonus(n_guessed)
            game.leaderboard.add_score(game.current_drawer, bonus)
            self.global_leaderboard.add_score(game.current_drawer, bonus)

        rankings = game.leaderboard.get_rankings(game.players)

        self.broadcast_to_room(room_name, {
            "action":"turn_ended",
            "word": game.current_word,
            "all_guessed": all_guessed,
            "rankings": rankings
        }, include_waiting=True)

        time.sleep(4)

        with game._lock:
            game._ending_turn = False

        has_next = game.next_turn()
        if has_next:
            # --- FIX: Waiting Room players are ONLY promoted into the active game
            # once a FULL ROUND has just finished (turn_index wraps back to 0,
            # meaning every current player has already had their turn this round).
            # This stops a new player from being yanked into a round that's
            # already in progress.
            if game.turn_index == 0:
                with game._lock:
                    if game.waiting_players:
                        promoted = game.waiting_players[:]
                        for wp in promoted:
                            game.players.append(wp)
                            game.leaderboard.reset_game_scores([wp])
                        game.waiting_players.clear()

                        for wp in promoted:
                            self.send_to(wp, {"action": "promoted", "players": game.players})

            self.broadcast_to_room(room_name, {"action":"clear_canvas"})
            
            # --- NEW: Check if this is the start of a new round for voting ---
            if game.turn_index == 0:
                self._begin_round_vote(room_name, game)
            else:
                self._begin_drawer_turn(room_name, game)
        else:
            self._end_game(room_name, game)

    def _end_game(self, room_name: str, game: GameState):
        with game._lock:
            if game.waiting_players:
                for wp in game.waiting_players:
                    game.players.append(wp)
                game.waiting_players.clear()

        final = game.leaderboard.get_rankings(game.players)
        all_time = self.global_leaderboard.get_all_time()
        
        self.broadcast_to_room(room_name, {
            "action":"game_over",
            "final_rankings": final,
            "all_time": all_time,
            "players": game.players 
        })
        game.status = GameState.LOBBY
        logger.info(f"Game over in room {room_name}. Back to lobby.")

if __name__ == "__main__":
    server = DrawticServer()
    server.start()
