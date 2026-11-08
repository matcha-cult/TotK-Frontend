# TotK Frontend

[简体中文](README.md)

> Status: **M3 complete**. The core library (`totk.ini` parsing/writing, settings registry, validation), presets, `doctor` diagnostics and the command-line tool are in place with unit tests; later milestones are in [docs/plan.md](docs/plan.md).

TotK Frontend is a **PC-style launcher and configuration front end** for [TotK Recomp](https://github.com/valentderah/totk-pc-recomp), the static recompilation of *The Legend of Zelda: Tears of the Kingdom* for PC. Its product shape follows the *Savage Wind Configuration* screen of [Savage Wind Recomp](https://github.com/Revivedx/SavageWindRecomp) (the BotW project): launch, video / audio / controls / mouse settings, presets, game-file guidance and log viewing before entering the game, so players rarely need to edit `totk.ini` by hand.

## What this is not

- **Not an emulator and not a recompiler**: the game itself is built and run by TotK Recomp; this project only manages its configuration and start-up flow.
- **Contains, requests and generates no Nintendo game files, keys, firmware or recompiled output.**
- **Not a change to the game's own in-game menus**: drawing PC settings into the game's native UI is a separate later topic (see "Non-goals" in [docs/plan.md](docs/plan.md)).

## Documentation tiers (important)

Documents are split into two kinds and **must live in different directories**:

| Directory | Tier | Committed | Content |
|---|---|---|---|
| `docs/` | Public, committable | Yes | Design, plan, tracking, settings reference, references, compliance |
| `private/` | Local only | **No** (ignored by `.gitignore`) | Machine paths, test records, unverified guesses, scratch notes |

Classification rules and the pre-commit checklist are in [docs/DOC-POLICY.md](docs/DOC-POLICY.md). Before committing, make sure `git status` shows no `private/` entries.

## Layout

```text
.
├── README.md / README.en.md   # bilingual documentation (workspace rule)
├── AGENTS.md                  # collaboration and AI-agent rules
├── src/totk_frontend/         # core library and CLI (ini, settings registry, validation, presets, doctor, command line)
├── tests/                     # headless unit tests and hand-written synthetic fixtures
├── tools/coverage_check.py    # statement-coverage check (stdlib only)
├── tools/check_env.py         # environment self-check (Python/tkinter/repo layout)
├── docs/                      # public documentation (committable)
│   ├── DOC-POLICY.md           # documentation tiers and commit checklist
│   ├── design.md               # product and technical design
│   ├── plan.md                 # development plan (phases/milestones, no time estimates)
│   ├── tracking.md             # task tracking (single source of truth)
│   ├── settings.md             # reference for totk.ini
│   ├── references.md           # reference projects and sources
│   ├── compliance.md           # compliance and copyright
│   └── handoff-prompt.md       # reusable handoff prompt
└── private/                    # local only (ignored, never committed)
```

## Progress

- M0: scaffolding and rules — done
- M1: core library (totk.ini parsing/writing, settings registry, validation, unit tests) — done
- M2: presets and `doctor` diagnostics — done
- M3: command-line tool (detect/list/get/set/preset/doctor/launch/log, etc.) — done
- M5: install detection and version awareness — in progress (detection and version awareness done, guidance page pending)
- M4: GUI (tkinter, six settings pages plus a log page) — done, verified on Windows
- M5: install detection, version awareness and first-run guidance — done
- From M6: packaging and release preparation (see [docs/plan.md](docs/plan.md))

## Running

Requires Python 3.11+ and the standard library only; the GUI needs tkinter (bundled with the official python.org installer).

```bash
# Command line
PYTHONPATH=src python -m totk_frontend --help
PYTHONPATH=src python -m totk_frontend doctor --dir <install-dir>

# GUI (needs tkinter and a desktop session)
PYTHONPATH=src python -m totk_frontend.gui
```

On Windows use `set PYTHONPATH=src` (PowerShell: `$env:PYTHONPATH = "src"`) and substitute `py -3` or the full interpreter path for `python`; no system PATH changes are needed.

## Reference projects

The project follows these projects in **product shape, settings semantics and documentation structure**; their code is not copied. Licences and reference notes are in [docs/references.md](docs/references.md).

- [Savage Wind Recomp](https://github.com/Revivedx/SavageWindRecomp) (MIT) — launcher/Configuration product shape and PC settings
- [TotK Recomp](https://github.com/valentderah/totk-pc-recomp) (MIT) — `totk.ini` settings model, install layout and launch flow
- [MacNativeGames](https://github.com/ly05010419/MacNativeGames) (MIT) — background on the TotK native layer
- [LAS Recomp](https://github.com/peiikai/LASRecomp) (MIT) — lineage and runtime background
- [UltraTears](https://github.com/kuraeow/ultratears) — reference for the `exefs/`, `romfs/` input layout (licence per its repository)
- [Ryujinx](https://github.com/Ryujinx/Ryujinx) (MIT) — background only (shader translator); its code is not used here

## Compliance

- No piracy assistance: no game files, keys, firmware, generated game code, saves, logs or screenshots in this repository.
- The tool only reads the player's own TotK Recomp install folder and only writes `totk.ini` and its backups.
- Disclaimer: not affiliated with Nintendo; *The Legend of Zelda* and *Tears of the Kingdom* are trademarks of Nintendo.

## Licence

**TBD** (see open question D3 in [docs/plan.md](docs/plan.md)). Until decided, nothing in this repository is licensed.
