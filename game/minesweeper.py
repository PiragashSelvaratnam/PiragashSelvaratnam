import json
import random
import re
import sys
import os
import urllib.parse
from collections import deque

REPO = "PiragashSelvaratnam/PiragashSelvaratnam"
BOARD_SIZE = 9
MINE_COUNT = 10
TOTAL_SAFE = BOARD_SIZE * BOARD_SIZE - MINE_COUNT  # 71

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
README_FILE = os.path.join(os.path.dirname(__file__), "..", "README.md")
MARKER_START = "<!-- MINESWEEPER_START -->"
MARKER_END = "<!-- MINESWEEPER_END -->"

COL_LABELS = list("ABCDEFGHI")
NUMBER_EMOJI = {
    0: "🟦",
    1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣",
    5: "5️⃣", 6: "6️⃣", 7: "7️⃣", 8: "8️⃣",
}


def parse_move(title):
    title = title.strip().lower()
    if re.match(r"^minesweeper\s+new(\s+game)?$", title):
        return ("new_game", None, None)
    m = re.match(r"^minesweeper\s+(reveal|flag)\s+(\d)\s+(\d)$", title)
    if m:
        action = m.group(1)
        row = int(m.group(2))
        col = int(m.group(3))
        if 0 <= row <= 8 and 0 <= col <= 8:
            return (action, row, col)
        raise ValueError(f"Coordinates out of range: {row}, {col}")
    raise ValueError(f"Unrecognised issue title: {title!r}")


def load_state():
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return new_game({})


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def new_game(state, first_row=None, first_col=None):
    stats = state.get("stats", {"games_won": 0, "games_lost": 0})
    new = {
        "board_size": BOARD_SIZE,
        "mine_count": MINE_COUNT,
        "mines": [],
        "cell_states": [["unrevealed"] * BOARD_SIZE for _ in range(BOARD_SIZE)],
        "adj_counts": [[0] * BOARD_SIZE for _ in range(BOARD_SIZE)],
        "game_status": "waiting_first_click",
        "revealed_count": 0,
        "stats": stats,
    }
    if first_row is not None and first_col is not None:
        _place_mines(new, first_row, first_col)
        new["game_status"] = "in_progress"
    return new


def _place_mines(state, safe_row, safe_col):
    excluded = set()
    for dr in range(-1, 2):
        for dc in range(-1, 2):
            r, c = safe_row + dr, safe_col + dc
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE:
                excluded.add((r, c))
    candidates = [
        (r, c)
        for r in range(BOARD_SIZE)
        for c in range(BOARD_SIZE)
        if (r, c) not in excluded
    ]
    mines = random.sample(candidates, MINE_COUNT)
    state["mines"] = mines
    _compute_adj_counts(state)


def _compute_adj_counts(state):
    mine_set = set(map(tuple, state["mines"]))
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if (r, c) in mine_set:
                state["adj_counts"][r][c] = -1
                continue
            count = 0
            for dr in range(-1, 2):
                for dc in range(-1, 2):
                    if dr == 0 and dc == 0:
                        continue
                    if (r + dr, c + dc) in mine_set:
                        count += 1
            state["adj_counts"][r][c] = count


def reveal(state, row, col):
    if state["game_status"] in ("won", "lost"):
        return state

    if state["game_status"] == "waiting_first_click":
        _place_mines(state, row, col)
        state["game_status"] = "in_progress"

    cell = state["cell_states"][row][col]
    if cell in ("revealed", "flagged"):
        return state

    mine_set = set(map(tuple, state["mines"]))

    if (row, col) in mine_set:
        state["cell_states"][row][col] = "hit_mine"
        state["game_status"] = "lost"
        state["stats"]["games_lost"] += 1
        for (mr, mc) in mine_set:
            if state["cell_states"][mr][mc] == "unrevealed":
                state["cell_states"][mr][mc] = "mine"
        return state

    queue = deque([(row, col)])
    visited = set()
    while queue:
        r, c = queue.popleft()
        if (r, c) in visited:
            continue
        visited.add((r, c))
        if state["cell_states"][r][c] in ("revealed", "flagged"):
            continue
        state["cell_states"][r][c] = "revealed"
        state["revealed_count"] += 1
        if state["adj_counts"][r][c] == 0:
            for dr in range(-1, 2):
                for dc in range(-1, 2):
                    nr, nc = r + dr, c + dc
                    if (
                        0 <= nr < BOARD_SIZE
                        and 0 <= nc < BOARD_SIZE
                        and (nr, nc) not in visited
                        and state["cell_states"][nr][nc] not in ("revealed", "flagged")
                        and (nr, nc) not in mine_set
                    ):
                        queue.append((nr, nc))

    _check_win(state)
    return state


def flag(state, row, col):
    if state["game_status"] in ("won", "lost"):
        return state
    cell = state["cell_states"][row][col]
    if cell == "unrevealed":
        state["cell_states"][row][col] = "flagged"
    elif cell == "flagged":
        state["cell_states"][row][col] = "unrevealed"
    return state


def _check_win(state):
    if state["revealed_count"] == TOTAL_SAFE:
        state["game_status"] = "won"
        state["stats"]["games_won"] += 1


def _issue_url(action, row, col):
    title = f"minesweeper {action} {row} {col}"
    params = urllib.parse.urlencode({"title": title, "labels": "minesweeper", "body": "."})
    return f"https://github.com/{REPO}/issues/new?{params}"


def _new_game_url():
    params = urllib.parse.urlencode({"title": "minesweeper new game", "labels": "minesweeper", "body": "."})
    return f"https://github.com/{REPO}/issues/new?{params}"


def _render_cell(state, row, col):
    cell = state["cell_states"][row][col]
    if cell == "revealed":
        n = state["adj_counts"][row][col]
        return NUMBER_EMOJI.get(n, "🟦")
    elif cell == "flagged":
        return f"[🚩]({_issue_url('flag', row, col)})"
    elif cell == "hit_mine":
        return "💥"
    elif cell == "mine":
        return "💣"
    else:
        return f"[⬜]({_issue_url('reveal', row, col)})"


def render_board_markdown(state):
    status = state["game_status"]
    stats = state["stats"]
    revealed = state["revealed_count"]

    lines = []
    lines.append("## 🎮 Minesweeper")
    lines.append("")

    if status == "lost":
        lines.append(f"> 💥 **Boom!** Someone hit a mine. [🔄 New Game?]({_new_game_url()})")
    elif status == "won":
        lines.append(f"> 🎉 **Board cleared!** All {TOTAL_SAFE} safe cells revealed! [🔄 Play Again?]({_new_game_url()})")
    else:
        lines.append("> Click a cell to reveal it — help clear the board without hitting a mine!")
        lines.append("> Clicking opens a pre-filled GitHub Issue, just submit it to make your move.")

    lines.append("")

    header = "|   | " + " | ".join(COL_LABELS) + " |"
    separator = "|---|" + "|".join([":---:"] * BOARD_SIZE) + "|"
    lines.append(header)
    lines.append(separator)

    for r in range(BOARD_SIZE):
        cells = [_render_cell(state, r, c) for c in range(BOARD_SIZE)]
        row_str = f"| **{r + 1}** | " + " | ".join(cells) + " |"
        lines.append(row_str)

    lines.append("")
    lines.append(
        f"💣 Mines: {MINE_COUNT} &nbsp;|&nbsp; "
        f"✅ Revealed: {revealed}/{TOTAL_SAFE} &nbsp;|&nbsp; "
        f"🎯 Won: {stats['games_won']} &nbsp;|&nbsp; "
        f"💥 Lost: {stats['games_lost']}"
    )
    lines.append("")
    lines.append(f"[🔄 New Game]({_new_game_url()})")

    return "\n".join(lines)


def update_readme(board_markdown):
    with open(README_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    if MARKER_START not in content or MARKER_END not in content:
        raise RuntimeError("Minesweeper markers not found in README.md")
    before = content.split(MARKER_START)[0]
    after = content.split(MARKER_END)[1]
    new_content = before + MARKER_START + "\n" + board_markdown + "\n" + MARKER_END + after
    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)


def main():
    if len(sys.argv) < 2:
        print("Usage: minesweeper.py '<issue title>'")
        sys.exit(1)

    title = sys.argv[1]
    try:
        action, row, col = parse_move(title)
    except ValueError as e:
        print(f"Skipping unrecognised move: {e}")
        sys.exit(0)

    state = load_state()

    if action == "new_game":
        state = new_game(state)
    elif action == "reveal":
        if state["game_status"] in ("won", "lost"):
            print("Game is already over — ignoring reveal, re-rendering current board.")
        else:
            state = reveal(state, row, col)
    elif action == "flag":
        if state["game_status"] in ("won", "lost"):
            print("Game is already over — ignoring flag.")
        else:
            state = flag(state, row, col)

    save_state(state)
    board_markdown = render_board_markdown(state)
    update_readme(board_markdown)
    print("Board updated successfully.")


if __name__ == "__main__":
    main()
