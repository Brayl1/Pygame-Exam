# Galaxy Defender 2.0 — Endless & Energy

A complete, resizable **Python + Tkinter** arcade game for **Group 3**. Choose a five-wave campaign or an endless survival run. Collect energy to evolve from one laser into a spread of fast shots, piercing lances, orbiting drones, and homing bolts.

![Endless mode title screen](docs/screenshots/menu.png)

## Start the game

Use **Python 3.10 or newer**; Python 3.12 is the tested baseline. Extract the entire ZIP, open the folder containing `main.py`, then run:

```sh
python -m pip install -r requirements.txt
python main.py
```

On Windows you can use `py` instead of `python`. After installing the requirement, double-clicking `run_game.bat` also launches the game.

**Upgrading from the earlier version:** extract into a new folder. Saved high scores remain in your user home folder and load automatically; the new Endless board starts empty. Copy your own WAV files into this version's `assets/sfx/` folder if you already added sounds. This package is based on the source shared in this conversation; local menu/code edits you made on your computer have not been imported. Keep your earlier folder for comparison.

**Framework:** Tkinter only. Pillow loads/resizes PNGs and renders the bundled licensed fonts. Check Tkinter with `python -m tkinter`; use a Python distribution with Tcl/Tk support. Ubuntu/Debian's system Python may need `python3-tk`. This is a desktop game and needs a graphical display.

## Choose a flight mode

| Mode | Starting hull | Objective |
| --- | ---: | --- |
| Standard | 100 | Clear five waves, including the final mothership and escorts |
| Relaxed | 150 | The same campaign with reduced incoming damage and projectile speed |
| Endless | 120 | Survive as many waves as possible; a boss arrives every fifth wave |

Each mode has its own top-ten score board. Endless never ends with a victory screen: play continues until your hull reaches zero or you end the run. Enemy health, damage, rewards, and firing pressure increase. Formation sizes, movement speed, bullet speed, and active entity pools are bounded. Clearing an Endless wave restores 6 hull, or 15 after a boss wave, up to your maximum.

## Controls

| Input | Action |
| --- | --- |
| WASD / arrow keys | Move, including diagonal movement |
| Automatic | Primary weapons fire during combat; no fire key is required |
| Space or R | Release Nova Burst at 100% charge |
| Q | Launch a homing missile; 5-second cooldown |
| E | Activate the highest-priority usable reserve pickup |
| P / Escape | Pause or resume |
| F11 | Toggle fullscreen |
| Enter | Launch from the menu or restart from results |
| M | Mute/unmute when optional sound files are installed |

Switching away from the window automatically pauses gameplay. The pause screen can end the run and save its score. Closing an active run also records it. A new run resets energy, weapon upgrades, consumable pickups, and Nova charge.

## Stack energy and evolve your weapons

Every enemy destroyed by your weapons drops a **violet energy crystal**. Scouts drop 1 energy, heavy ships 2, and bosses 6. Fly near a crystal to attract it. During intermission, all remaining energy is drawn toward your ship. Energy has its own counter and works even when the four-slot reserve is full.

Energy is cumulative for the current run. Taking damage and using Nova do not reduce it. Thresholds below are cumulative totals, not purchases or costs.

| Level | Total energy | Core | Shots per normal salvo | Nominal salvos/s | New ability |
| --- | ---: | --- | ---: | ---: | --- |
| 1 | 0 | PULSE | 1 | 4.5 | Single laser |
| 2 | 3 | TWIN | 2 | 4.9 | Twin barrels |
| 3 | 7 | TRIDENT | 3 | 5.4 | Three-way spread |
| 4 | 12 | QUAD | 4 | 6.1 | Four-way spread |
| 5 | 18 | FANFIRE | 5 | 6.9 | Five-barrel salvo |
| 6 | 26 | PRISM | 5 | 7.7 | One shot becomes a three-target piercing lance every third salvo |
| 7 | 36 | ORBIT | 8 | 8.7 | Six main shots and two orbiting drone cannons |
| 8 | 48 | TEMPEST | 9 | 10.0 | Seven main shots, two drone shots, plus two homing bolts every 1.6 seconds when a target is visible |

Projectile speed also grows from 680 to 960 world units per second for the main weapon. Rapid fire adds **two more barrels** and reduces the firing interval to 62% of normal for eight seconds. At level eight, that means **11 shots per boosted salvo**, plus periodic homing bolts. Actual cadence depends on frame timing.

Weapon level caps at eight to keep the screen and performance manageable. Additional energy still awards points and replenishes Nova charge. Open **How to Play → Arsenal** to view all tiers in the game.

![Maximum-level projectile patterns](docs/screenshots/combat.png)

## Nova, missiles, and reserve pickups

- Each energy unit adds 10 percentage points of Nova charge, capped at 100%.
- Press Space/R when ready to fire 24 radial bolts, clear hostile projectiles, and gain one second of protection. Nova consumes its charge, keeping your accumulated energy and weapon level.
- Q uses Selection Sort to target the highest-value visible enemy. Its missile retargets if that ship dies and deals splash damage to nearby ships on impact.
- Every third total kill drops a reserve pickup in addition to energy. Fly into it, then press E to activate it.
- Reserve priority: repair, shield, rapid fire. Repair restores 35 hull; shield lasts 6 seconds; rapid fire lasts 8 seconds. A full hull skips repair and keeps it for later.
- Repeated shields/rapid-fire effects extend their timers up to 12/16 seconds. Discover all three reserve types for a one-time 300-point bonus.
- Escaping enemies damage your hull even while shielded. Collisions that destroy enemies by ramming do not award a player kill or energy.
- Bosses alternate aimed projectile fans and slower circular ion rings. Watch for the gaps, and keep Nova ready when the screen gets crowded.

## Scoring and persistent records

| Event | Points |
| --- | ---: |
| Scout destroyed | 100 × multiplier, before Endless scaling |
| Heavy destroyed | 260 × multiplier, before Endless scaling |
| Boss destroyed | 2,400 × multiplier, before Endless scaling |
| Energy collected | 10 per energy unit |
| Campaign wave cleared | 250 |
| Endless wave cleared | 250 + 35 × wave number |
| First reserve pickup type | 60 |
| Repeat reserve pickup type | 20 |
| Discover all three reserve types | 300 once |
| Campaign victory | 1,000 + 10 × remaining hull |

Quick kills increase the multiplier: ×2 from the fourth, ×3 from the eighth, and ×4 from the twelfth consecutive kill. A gap over 4.5 seconds or taking damage resets it. Endless enemy values rise by 5% of their base per additional wave, rounded to an integer.

The game saves the ten highest runs per mode, including callsign, score, wave reached, outcome, and date. Records are stored in `.galaxy_defender/profile.json` in your user home directory. Missing/corrupt files do not prevent play; failed writes preserve the session's board and display a notice. `GALAXY_DEFENDER_DATA_DIR` can select another save folder for testing. Earlier records still load, with a dash in the wave column when that information was not recorded.

## Required course concepts

| Concept | Live game feature | Code |
| --- | --- | --- |
| Bubble Sort | Rank visible threats; choose the radar entry and warning marker | `algorithms.bubble_sort`, `GameModel.update_threat_ranking` |
| Insertion Sort | Power-up reserve priority, timed spawn order, high-score boards | `insert_ordered`, `insertion_sort`, `ScoreStore` |
| Selection Sort | Highest-value target for missiles and homing bolts | `selection_sort`, `GameModel.choose_target` |
| Tuples | Positions, velocities, formation offsets, firing angles | `model.py`, `formations.py`, `weapons.py` |
| Sets | Unique power-up discoveries; prevent repeated hits by a piercing projectile | `unique_powerups`, projectile `hit_ids` |
| Dictionaries | Player/enemy stats, weapon tier definitions, projectile/pickup state | `ENEMY_STATS`, `POWERUPS`, `WEAPON_TIERS` |
| Recursion | Expand nested campaign and Endless formations into real spawns | `expand_formation` |

The three sorts are explicit implementations; built-in sorting is not substituted in production code. Endless generates one bounded formation tree per wave, so recursion depth does not grow with survival time. The Tkinter `after` update loop is not recursive. See [FEATURE_MAP.md](docs/FEATURE_MAP.md) for call sites and traces.

## Project layout

| File/folder | Responsibility |
| --- | --- |
| `main.py` | Entry point and readable launch errors |
| `galaxy/app.py` | Single-window GUI, menu, HUD, Arsenal, controls, rendering |
| `galaxy/model.py` | Combat, auto-fire, energy, Nova, collision, wave transitions |
| `galaxy/weapons.py` | Eight weapon tiers, spread patterns, entity limits |
| `galaxy/formations.py` | Campaign/Endless formation trees and recursive expansion |
| `galaxy/algorithms.py` | Required hand-written sorts |
| `galaxy/storage.py` | Atomic JSON score storage and legacy loading |
| `galaxy/assets.py` | Original PNGs, scalable lettering, image caches |
| `galaxy/audio.py` | Existing optional SFX adapter |
| `assets/` | Ten original PNGs, generation provenance, fonts and licenses |
| `tests/` | Algorithms, gameplay, Endless progression, persistence, real GUI checks |
| `docs/` | Rubric, feature map, test record, upgrade notes, contribution log |

## Optional audio

This build contains no WAV files. Existing audio events are available through the original optional adapter; place your own WAVs in `assets/sfx/` using the names in its README. The separate wave-clear sound updater is not part of this release. The adapter plays one effect at a time. No Pygame dependency is used.

## Tests

```sh
python -m unittest discover -v
```

There are 48 tests, including four real Tkinter GUI tests. GUI checks skip on display-less Linux systems. The new cases verify energy thresholds, auto-fire, piercing, splash damage, drone/bolt creation, Nova, bounded entity counts, old-save compatibility, boss scheduling, and continuation past wave 30. Read [the test record](docs/TESTING.md) and [upgrade notes](docs/UPGRADE_V2.md).

## Group members and roles - complete before submission

The guide requires a real coding contribution from every member, including design, documentation, QA, and coordination. Fill in actual names and completed work; the table below is a suggested allocation, not a claim of authorship.

| Member name | Primary role | Suggested coding responsibility | Test/defense responsibility |
| --- | --- | --- | --- |
| Add name | Coordinator and integrator | Wave transitions or integration fixes | Complete mission, clean checkout |
| Add name | Gameplay programmer | Movement, collision, combat or boss behavior | Win/loss paths and damage |
| Add name | Data structures and algorithms | Sorts, reserve priorities or formations | Algorithm traces and base cases |
| Add name | Interface and asset designer | A screen, control, layout or asset-loader improvement | Resize, navigation, controls |
| Add name | QA, documentation and release | Score-storage improvement, small feature or bug fix | Regression tests, README, repository |

For four members, combine coordinator and QA/release duties, while retaining a coding contribution for each member. Use [the contribution log](docs/CONTRIBUTIONS.md) to record actual work. This package is an AI-assisted implementation; team members should understand and be able to explain the code they use and modify.

## GitHub submission

This ZIP contains the source and assets. **It is not a published GitHub repository.** Create one repository for the team, fill in the member table, and commit actual work throughout development. Do not submit only an executable, video, or screenshot.

In a new empty GitHub repository, copy its URL and run these commands in this project folder. Replace the example account/repository URL first:

```sh
git init
git add .
git commit -m "Add Galaxy Defender Tkinter game"
git branch -M main
git remote add origin https://github.com/YOUR-ACCOUNT/galaxy-defender.git
git push -u origin main
```

Do not use those initialization commands over an existing team repository; add this project to that repository and follow its normal commit workflow instead. Never include passwords, API keys, personal save files, or `.venv`. The included `.gitignore` excludes common generated files.

Before submission, clone/download the repository into a clean folder, install `requirements.txt`, run `main.py`, and complete one run. Confirm the instructor can access it; give access first if the repository is private. Submit that repository link. See [the rubric and demonstration guide](docs/RUBRIC_AND_DEMO.md) for the remaining team tasks.

## Credits and references

- Artwork: generated with OpenAI image generation for this Galaxy Defender Group 3 project. The exact generation prompts and asset metadata are included in `assets/`. No downloaded third-party art is bundled.
- Fonts: DejaVu Sans Regular and Bold, bundled for consistent Canvas lettering. Their license and attribution are included in `assets/fonts/LICENSE.txt`.
- Source implementation: AI-assisted Python/Tkinter project prepared for team review, adaptation, and demonstration.
- [Python Tkinter documentation](https://docs.python.org/3/library/tkinter.html)
- [Pillow ImageTk documentation](https://pillow.readthedocs.io/en/stable/reference/ImageTk.html)
- Course requirements: the supplied *Python Game Development Midterm Lab Exam Guide*, Group 3 Galaxy Defender.
