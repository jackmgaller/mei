# Workboard

A local web page showing the agents working on Mei, each in its own worktree and branch: a board
by state, the assets they have built, which cells of a world they have touched, their open
questions, and how long each took.

```sh
python3 tools/workboard/serve.py --port 8770      # http://127.0.0.1:8770/
python3 tools/workboard/serve.py --branches 'shrinetown-*' --since 4
python3 tools/workboard/serve.py --once > board.json
```

It binds 127.0.0.1 only and needs nothing beyond Python 3.10 and git. It scans every `--refresh`
seconds (default 10; a scan of about 50 worktrees takes 2–5 s) and the page polls every 5 s.
`?view=assets` (or `level`, `questions`, `stats`) opens a view directly.

## Two sources

**Reported**, by the agents through `tools/work_status.py` (the commands are in
[AGENTS.md](../../AGENTS.md#reporting-status)): title, kind, model, lead, state, percent, the
current step, items (one per asset, with a size class), questions and notes. One record per
agent, `status/ID.json`, and its history, `log/ID.jsonl`, in `$MEI_WORK_DIR`, else
`<git common dir>/mei-work/` (`.git/mei-work/` of the main checkout): every worktree reaches it
and git never commits it. Writers take a lock and replace the file atomically.

**Inferred**, for every worktree whether it reports or not:

| What | From |
|---|---|
| Worktrees, branches, start time | `git worktree list`; the creation time of the worktree's admin directory |
| Running or not | Claude Code locks an agent's worktree with `claude agent … (pid N …)`; a lock whose process is alive is "live" |
| Own commits | Commits on the branch made after the worktree was created and not on any branch that doesn't contain it |
| Merged | The base branch (`--base`, default `main`) contains the tip, committed after the worktree was created |
| Uncommitted work | `git status` (with `--no-optional-locks`, so the scan doesn't touch the index) |
| Last activity | The newest of: commits, HEAD changes, uncommitted files' times, kit reports, the status record |
| Kind | The files touched: cells or worlds, then asset recipes, then `tools/` `src/` `tests/`, then docs |
| Assets | Recipes (`*.asset.json`) changed on the branch; every Asset Kit `report.json` under the worktree's `build*/` (triangles, budget, verification, size class from the bounds: small ≤ 2 units, medium ≤ 8, large); `contact.png` and `cameras.png` beside the report or in the recipe's `preview/` |
| Worlds | Every `*.world.json` in the main checkout or changed on a branch; its cells from `cell_dir`; which branch changed which cell file; triangles per cell from the newest `mei-world-report` found |

A card is stale when it is queued, working or blocked and nothing has happened for `--stale`
minutes (default 20). A reported state wins over the inferred one, except that a branch already
merged shows as merged. A record joins a worktree by its `worktree` or `branch`; a record with
neither (an agent not started yet) is a card of its own.

Without a record a card's state is guessed: merged; working when live; stopped when locked by a
dead process; review when it has commits and nothing uncommitted; working when active in the
last `--stale` minutes; else review or stopped. The model is only known from a record.

Which worktrees show: the ones active in the last `--since` hours (default 12), live, or with a
record; `--all` shows every one, `--branches GLOB` narrows them, the main checkout is left out
unless `--include-main`. The page hides finished cards older than 3 hours unless "Older finished
work" is ticked.

## Files

| File | What |
|---|---|
| `serve.py` | The HTTP server: `/` and `/static/`, `/api/state`, `/api/history?key=`, `/img?w=&p=`, `POST /api/answer` |
| `infer.py` | The scan: git, build outputs, worlds; `snapshot()` returns the board as JSON |
| `status.py` | The status store, shared with `tools/work_status.py` |
| `static/` | The page: `index.html`, `app.js`, `style.css`, no libraries |

`/img` serves only `.png`, `.jpg`, `.gif` and `.webp` files inside a worktree on the board.
The answer box on the Questions view writes the answer into the agent's record (the one write
the page makes); `work_status.py show ID` prints it for the agent. Tests:
`python3 -m unittest discover -s tests -p test_workboard.py` (in `make test`).

## Not done yet

- Answers are not pushed to the agent; it has to run `show`, or the lead passes them on.
- The level view colours cell files only; a world whose cells are inline, or work in shared
  asset folders, shows in the legend's counts rather than on the grid.
- Size classes from the bounds are a guess until the agent reports `--size`.
