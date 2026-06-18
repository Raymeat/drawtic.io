# DRAWTIC.io

A lightweight, multiplayer desktop game inspired by Skribbl.io. Built entirely with Python, this project uses raw TCP sockets for real-time networking and Tkinter for a clean, responsive graphical user interface.

## Member

Fawwaz Reynardio Ednansyah 5025241167<br>
Naufal Bintang Brillian 5025241168<br>
Rayen Yeriel Mangiwa 5025241262<br>
Makna Alam Pratama 5025140177<br>

## Features

* **User Authentication:** Secure login and registration system with SHA-256 password hashing.
* **Real-Time Multiplayer:** Synchronized drawing and chatting across multiple clients using threaded TCP sockets and framed JSON payloads.
* **Interactive Canvas:** Fully functional drawing board supporting multiple colors, brush sizes, an eraser, and a canvas-clear functionality.
* **Game Logic Engine:** * Turn-based gameplay with configurable rounds.
    * Word choice selection for the drawer.
    * Progressive hints (revealing letters over time) for guessers.
    * Dynamic scoring system rewarding faster correct guesses.
* **Leaderboards:** Real-time ranking updates at the end of each round and an all-time top 10 leaderboard.

## Tech Stack

* **Language:** Python 3.x
* **GUI:** `tkinter` (Built-in)
* **Networking:** `socket`, `struct` (Custom length-prefixed message framing)
* **Concurrency:** `threading`
* **Data Serialization:** `json`

## How to Run

### Prerequisites
Ensure you have Python 3.x installed on your system. 
*Note: If you are on Windows, ensure that the **tcl/tk and IDLE** option was checked during your Python installation, as it is required for the Tkinter GUI.*

### 1. Start the Server
The server must be running before any clients can connect. It handles all game states, broadcasting, and user data.
```bash
python server.py
The server will start listening on 0.0.0.0:9999 by default.

2. Start the Client(s)
Open a new terminal window for each player and run the client script:

Bash
python client.py
Enter the host IP (use 127.0.0.1 if running locally).

Register a new account or log in.

Wait for at least 2 players to join the lobby, then hit Start Game!

How to Play
Drawer: When it's your turn, choose a word from the prompt. Use the tools at the top of the canvas to draw the word. You cannot type in the chat while drawing.

Guesser: Watch the canvas and type your guesses into the chat box. Pay attention to the top bar for progressive letter hints and word length.

Scoring: The faster you guess the word correctly, the more points you get. The drawer also gets bonus points if players successfully guess the word.
