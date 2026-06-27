# DRAWTIC.io

A lightweight, multiplayer desktop drawing-and-guessing game built entirely with Python. This project uses raw TCP sockets for real-time networking, UDP broadcast for automatic LAN server discovery, and Tkinter for a clean, responsive graphical user interface.

## Member
Fawwaz Reynardio Ednansyah 5025241167<br>
Naufal Bintang Brillian 5025241168<br>
Rayen Yeriel Mangiwa 5025241262<br>
Makna Alam Pratama 5025241077<br>

## Features

* **User Authentication** — Secure register/login system with SHA-256 password hashing, persisted to a local `user.txt` file.
* **Multi-Room Lobby** — Create or join multiple independent game rooms from a single server instance; rooms are listed live and auto-removed once empty.
* **LAN Auto-Discovery** — Clients can find the server automatically on the local network via a UDP broadcast probe, no need to type the host IP manually.
* **Real-Time Multiplayer** — Synchronized drawing and chat across clients using threaded TCP sockets with length-prefixed JSON message framing.
* **Interactive Canvas** — Fully functional drawing board with multiple colors, a custom color picker, adjustable brush size, an eraser, and a clear-canvas action.
* **Category Voting** — At the start of every round, players vote between 3 randomly drawn categories (10-second timer); the most-voted category wins, with ties broken randomly.
* **Game Logic Engine**
  * Turn-based gameplay with configurable round duration and rounds per game.
  * Player order is shuffled at the start of each game.
  * Word selection pulled from the winning category, avoiding recently used words.
  * Progressive hints — random letters of the word are revealed over time for guessers.
  * Dynamic scoring that rewards faster correct guesses, plus a bonus for the drawer based on how many players guessed correctly.
* **Fair Waiting Room** — Players who join a room while a game is already in progress are placed in a spectator Waiting Room instead of being dropped into the middle of someone's turn. They are only promoted into the active player list once the **entire current round finishes** (i.e. every current player has had their turn and play wraps back to a new round), keeping turn order fair for everyone already in the game.
* **Leaderboards** — Live ranking updates after every turn, plus a persistent all-time Top 10 leaderboard tracked across games.
* **Graceful Disconnects** — If the current drawer disconnects mid-turn, the turn ends cleanly and the game continues for everyone else; rooms with no players left are automatically cleaned up.

## Tech Stack
* **Language:** Python 3.x
* **GUI:** `tkinter` (Built-in)
* **Networking:** `socket` (TCP for gameplay, UDP for LAN discovery), custom length-prefixed message framing
* **Concurrency:** `threading`
* **Data Serialization:** `json`
* **Auth:** `hashlib` (SHA-256)

## How to Run

### Prerequisites
Ensure you have Python 3.x installed on your system.

*Note: If you are on Windows, ensure that the **tcl/tk and IDLE** option was checked during your Python installation, as it is required for the Tkinter GUI.*

### 1. Start the Server
The server must be running before any clients can connect. It handles all room/game state, broadcasting, and user data.

```bash
python server.py
```

The server listens on `0.0.0.0:9999` for gameplay connections and `9998` (UDP) for LAN auto-discovery. On first run it will automatically generate a default `words.json` (word categories) and `user.txt` (account store) if they don't already exist.

### 2. Start the Client(s)
Open a new terminal window for each player and run:

```bash
python client.py
```

* Enter the host IP, or click **🔍 Auto-Detect** to find a server on your local network automatically (use `127.0.0.1` if running locally on the same machine).
* Register a new account or log in.
* Create a room or join an existing one from the lobby.
* Wait for at least 2 players in the room, then hit **▶ Start Game**!

## How to Play
1. **Category Voting:** At the start of each round, every player votes for one of three suggested categories.
2. **Drawer:** When it's your turn, you'll see the secret word — use the tools above the canvas to draw it. You cannot chat while drawing.
3. **Guesser:** Watch the canvas and type your guesses into the chat box. Keep an eye on the top bar for progressively revealed letter hints and the word length.
4. **Scoring:** The faster you guess correctly, the more points you earn. The drawer also earns bonus points based on how many players guessed correctly.
5. **Joining Mid-Game:** If you join a room while a game is already running, you'll land in the Waiting Room and automatically join the action once the current round wraps up.

## Project Files
* `server.py` — Game server: room/connection management, turn & round logic, scoring, word bank, and LAN discovery service.
* `client.py` — Tkinter desktop client: auth screen, lobby, drawing canvas, chat, and live leaderboards.
* `words.json` *(auto-generated)* — Editable word bank, organized by category.
* `user.txt` *(auto-generated)* — Stores registered accounts (hashed passwords only).

## User & Password
1. budi = budi123
2. asep = asep123
3. hari = hari123
