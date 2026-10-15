"""One resizable Tk window, Canvas artwork, and a non-blocking after loop."""

import math
import random
import time
import tkinter as tk
from pathlib import Path
from .assets import AssetManager, TextRenderer
from .audio import AudioManager
from .model import GameModel, POWERUPS
from .formations import WORLD_WIDTH, WORLD_HEIGHT, WAVE_COUNT
from .storage import ScoreStore, clean_name
from .weapons import WEAPON_TIERS

BASE_WIDTH, BASE_HEIGHT = 1280, 800
FIELD_X, FIELD_Y = 32, 105
INK = "#edf5ff"
MUTED = "#8fa6c2"
CYAN = "#60e5fa"
GOLD = "#ffc56b"
RED = "#ff738d"
VIOLET = "#b493ff"
PANEL = "#0b1527"
LINE = "#253951"


class GalaxyApp:
    def __init__(self, root: tk.Tk, data_directory: Path | None = None, auto_loop: bool = True):
        self.root = root
        root.title("Tigbantay Sa Kalibutan | Group 3")
        width = min(1280, max(960, root.winfo_screenwidth() - 80))
        height = min(800, max(620, root.winfo_screenheight() - 90))
        root.geometry(f"{width}x{height}")
        root.minsize(960, 620)
        root.configure(bg="#030713")
        self.canvas = tk.Canvas(root, bg="#030713", highlightthickness=0, takefocus=True)
        self.canvas.pack(fill="both", expand=True)
        self.assets = AssetManager(Path(__file__).resolve().parent.parent / "assets", root)
        self.lettering = TextRenderer(Path(__file__).resolve().parent.parent / "assets/fonts", root)
        self.audio = AudioManager(Path(__file__).resolve().parent.parent / "assets/sfx")
        self.store = ScoreStore(data_directory)
        self.screen = "menu"
        self.mode = "standard"
        self.model = None
        self.saved = False
        self.new_best = False
        self.run_best = 0
        self.keys = set()
        self.buttons = []
        self.mouse = (-1, -1)
        self.scale = 1.0
        self.offset_x, self.offset_y = 0.0, 0.0
        self.width, self.height = width, height
        self.background_photo = None
        self.background_id = None
        self.last_tick = time.perf_counter()
        self.animation_clock = 0.0
        self.after_id = None
        self.resize_id = None
        self.focus_id = None
        self.closed = False
        self.fullscreen = False
        self.font = "Segoe UI"
        self.name_var = tk.StringVar(value=self.store.name)
        self.name_entry = tk.Entry(self.canvas, textvariable=self.name_var, bg="#12233a", fg=INK,
                                   insertbackground=CYAN, relief="flat", highlightthickness=1,
                                   highlightbackground=LINE, highlightcolor=CYAN,
                                   font=(self.font, -16), bd=10)
        self.name_window = self.canvas.create_window(0, 0, window=self.name_entry, anchor="nw", state="hidden")
        self.visual_rng = random.Random(103)
        self.stars = [(self.visual_rng.uniform(0, WORLD_WIDTH), self.visual_rng.uniform(0, WORLD_HEIGHT),
                       self.visual_rng.uniform(7, 26)) for _ in range(38)]
        self.icon = self.assets.sprite("player", 48, 1)
        root.iconphoto(True, self.icon)
        root.bind("<KeyPress>", self.on_key_press)
        root.bind("<KeyRelease>", self.on_key_release)
        root.bind("<FocusOut>", self.on_focus_out)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.canvas.bind("<Configure>", self.on_resize)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Leave>", lambda _e: setattr(self, "mouse", (-1, -1)))
        self.canvas.bind("<Button-1>", self.on_click)
        root.update_idletasks()
        self.resize_now()
        self.draw()
        self.canvas.focus_set()
        if auto_loop:
            self.tick()

    def xy(self, x, y):
        return self.offset_x + x * self.scale, self.offset_y + y * self.scale

    def rect(self, x, y, w, h, fill=PANEL, outline="", width=1, **kwargs):
        return self.canvas.create_rectangle(*self.xy(x, y), *self.xy(x + w, y + h),
                                             fill=fill, outline=outline, width=width * self.scale,
                                             tags="frame", **kwargs)

    def text(self, x, y, value, size=14, color=INK, anchor="nw", bold=False, width=None, **kwargs):
        photo = self.lettering.render(str(value), max(9, round(size * self.scale)), color, bold,
                                      round(width * self.scale) if width else 0)
        return self.canvas.create_image(*self.xy(x, y), image=photo, anchor=anchor,
                                        tags=("frame", "label"), **kwargs)

    def line(self, x1, y1, x2, y2, color=LINE, width=1, **kwargs):
        self.canvas.create_line(*self.xy(x1, y1), *self.xy(x2, y2), fill=color,
                                width=max(1, width * self.scale), tags="frame", **kwargs)

    def oval(self, x, y, w, h, outline=CYAN, fill="", width=1):
        self.canvas.create_oval(*self.xy(x, y), *self.xy(x + w, y + h), outline=outline,
                                fill=fill, width=max(1, width * self.scale), tags="frame")

    def sprite(self, name, x, y, width):
        photo = self.assets.sprite(name, width, self.scale)
        self.canvas.create_image(*self.xy(x, y), image=photo, tags="frame")

    def button(self, x, y, w, h, label, action, primary=False, danger=False, small=False):
        hovered = x <= self.mouse[0] <= x + w and y <= self.mouse[1] <= y + h
        fill = ("#98f2ff" if hovered else CYAN) if primary else ("#20344c" if hovered else "#102036")
        edge = RED if danger else (CYAN if hovered else LINE)
        self.rect(x, y, w, h, fill, edge if not primary else "")
        self.text(x + w / 2, y + h / 2, label, 11 if small else 14,
                  "#061322" if primary else (RED if danger else INK), anchor="center", bold=True)
        self.buttons.append((x, y, w, h, action))

    def bar(self, x, y, w, fraction, color, height=6):
        self.rect(x, y, w, height, "#1b2d42")
        self.rect(x, y, w * max(0, min(1, fraction)), height, color)

    def on_resize(self, _event):
        if self.resize_id:
            self.root.after_cancel(self.resize_id)
        self.resize_id = self.root.after(90, self.resize_now)

    def resize_now(self):
        self.resize_id = None
        self.width = max(1, self.canvas.winfo_width())
        self.height = max(1, self.canvas.winfo_height())
        self.scale = min(self.width / BASE_WIDTH, self.height / BASE_HEIGHT)
        self.offset_x = (self.width - BASE_WIDTH * self.scale) / 2
        self.offset_y = (self.height - BASE_HEIGHT * self.scale) / 2
        self.background_photo = self.assets.backdrop(round(BASE_WIDTH * self.scale), round(BASE_HEIGHT * self.scale))
        if self.background_id is not None:
            self.canvas.delete(self.background_id)
        self.background_id = self.canvas.create_image(*self.xy(0, 0), image=self.background_photo, anchor="nw", tags="background")
        self.canvas.tag_lower("background")
        self.canvas.coords(self.name_window, *self.xy(88, 425))
        self.canvas.itemconfigure(self.name_window, width=round(292 * self.scale), height=round(44 * self.scale))
        self.name_entry.configure(font=(self.font, -max(12, round(16 * self.scale))))
        self.draw()

    def on_motion(self, event):
        self.mouse = ((event.x - self.offset_x) / self.scale, (event.y - self.offset_y) / self.scale)
        hover = any(x <= self.mouse[0] <= x + w and y <= self.mouse[1] <= y + h for x, y, w, h, _ in self.buttons)
        self.canvas.configure(cursor="hand2" if hover else "")

    def on_click(self, event):
        self.on_motion(event)
        for x, y, w, h, callback in self.buttons[:]:
            if x <= self.mouse[0] <= x + w and y <= self.mouse[1] <= y + h:
                callback()
                return
        self.canvas.focus_set()

    def on_key_press(self, event):
        key = event.keysym.lower()
        if event.widget is self.name_entry and key not in {"return", "escape", "f11"}:
            return
        fresh = key not in self.keys
        self.keys.add(key)
        if not fresh:
            return
        if key == "f11":
            self.fullscreen = not self.fullscreen
            self.root.attributes("-fullscreen", self.fullscreen)
        elif key in {"p", "escape"}:
            if self.screen in {"game", "pause"}:
                self.toggle_pause()
            elif self.screen != "menu":
                self.show("menu")
        elif key == "return" and self.screen in {"menu", "result"}:
            self.start_game()
        elif self.screen == "game" and self.model:
            if key == "q":
                self.model.launch_missile()
            elif key in {"r", "space"}:
                self.model.launch_nova()
            elif key == "e":
                self.model.activate_powerup()
            elif key == "m" and self.audio.available:
                self.audio.enabled = not self.audio.enabled

    def on_key_release(self, event):
        self.keys.discard(event.keysym.lower())

    def on_focus_out(self, _event):
        if not self.closed:
            if self.focus_id:
                self.root.after_cancel(self.focus_id)
            self.focus_id = self.root.after(70, self.check_focus)

    def check_focus(self):
        self.focus_id = None
        if self.closed:
            return
        if self.root.focus_displayof() is None:
            self.keys.clear()
            if self.screen == "game":
                self.toggle_pause()

    def show(self, screen):
        self.screen = screen
        self.keys.clear()
        self.canvas.focus_set()
        self.draw()

    def select_mode(self, mode):
        self.mode = mode
        self.draw()

    def start_game(self):
        self.name_var.set(clean_name(self.name_var.get()))
        self.model = GameModel(self.mode)
        self.run_best = self.store.best(self.mode)
        self.saved, self.new_best = False, False
        self.last_tick = time.perf_counter()
        self.show("game")

    def toggle_pause(self):
        if not self.model:
            return
        if self.screen == "game" and self.model.status == "playing":
            self.model.status = "paused"
            self.show("pause")
        elif self.screen == "pause":
            self.model.status = "playing"
            self.last_tick = time.perf_counter()
            self.show("game")

    def end_run(self):
        if self.model:
            self.model.finish("defeat")
            self.save_result()
            self.show("result")

    def save_result(self):
        if self.saved or not self.model:
            return
        self.new_best = self.store.record(self.name_var.get(), self.model.score,
                                          self.model.mode, self.model.status, self.model.wave)
        self.saved = True

    def tick(self):
        if self.closed:
            return
        now = time.perf_counter()
        dt = min(.05, now - self.last_tick)
        self.last_tick = now
        self.animation_clock += dt
        if self.screen == "game" and self.model:
            self.model.step(dt, self.keys)
            if self.model.status in {"victory", "defeat"}:
                self.save_result()
                self.screen = "result"
                self.keys.clear()
        if self.model:
            for event in self.model.events:
                self.audio.play(event)
            self.model.events.clear()
        self.draw()
        self.after_id = self.root.after(16, self.tick)

    def close(self):
        if self.closed:
            return
        if self.model and self.model.status in {"playing", "paused"}:
            self.model.finish("defeat")
            self.save_result()
        self.closed = True
        if self.after_id:
            self.root.after_cancel(self.after_id)
        if self.resize_id:
            self.root.after_cancel(self.resize_id)
        if self.focus_id:
            self.root.after_cancel(self.focus_id)
        self.audio.close()
        self.root.destroy()

    def header(self):
        self.oval(40, 33, 27, 27, CYAN, "#123048", 2)
        self.text(53.5, 46.5, "G", 15, CYAN, "center", True)
        self.text(82, 31, "Tigbantay Sa Kalibutan", 16, INK, bold=True)
        self.text(82, 55, "GROUP 03  /  ORBITAL DEFENSE", 10, MUTED)
        self.line(32, 84, 1248, 84)

    def draw(self):
        if self.closed:
            return
        self.canvas.delete("frame")
        self.buttons = []
        self.canvas.itemconfigure(self.name_window, state="normal" if self.screen == "menu" else "hidden")
        if self.screen in {"game", "pause"} and self.model:
            self.draw_game()
            if self.screen == "pause":
                self.draw_pause()
        else:
            self.header()
            if self.screen == "menu":
                self.draw_menu()
            elif self.screen == "instructions":
                self.draw_instructions()
            elif self.screen == "concepts":
                self.draw_concepts()
            elif self.screen == "arsenal":
                self.draw_arsenal()
            elif self.screen == "leaderboard":
                self.draw_leaderboard()
            elif self.screen == "result":
                self.draw_result()
        # Put the native text field above decorative Canvas elements.
        self.canvas.tag_raise(self.name_window)

    def draw_menu(self):
        self.text(1224, 29, "LOCAL HIGH SCORE", 11, MUTED, "ne")
        self.text(1224, 46, f"{self.store.best(self.mode):,}", 27, CYAN, "ne", True)
        self.text(88, 146, "THE LAST LINE OF DEFENSE", 12, CYAN, bold=True)
        self.text(84, 187, "Tigbantay Sa", 67, INK, bold=True)
        self.text(84, 258, "Kalibutan", 67, INK, bold=True)
        tagline = "Survive the infinite fleet. Stack energy.\nEvolve your arsenal." if self.mode == "endless" else "Hold the perimeter. Collect energy.\nBring your pilot home."
        self.text(91, 350, tagline, 17, MUTED, width=565)
        self.text(88, 402, "PILOT CALLSIGN", 11, MUTED, bold=True)
        self.text(406, 402, "FLIGHT MODE", 11, MUTED, bold=True)
        for mode, x in (("standard", 406), ("relaxed", 492), ("endless", 578)):
            selected = self.mode == mode
            self.button(x, 425, 78, 44, mode.upper(), lambda m=mode: self.select_mode(m), primary=selected, small=True)
        self.button(88, 503, 292, 56, "LAUNCH MISSION   >", self.start_game, primary=True)
        self.button(406, 503, 250, 56, "HOW TO PLAY", lambda: self.show("instructions"))
        self.button(88, 576, 292, 46, "HIGH SCORES", lambda: self.show("leaderboard"))
        self.button(406, 576, 250, 46, "EXIT GAME", self.close)
        descriptions = {"standard": "STANDARD  /  Five waves. One mothership. 100 hull.",
                        "relaxed": "RELAXED  /  Five waves with 150 hull and gentler fire.",
                        "endless": "ENDLESS  /  Escalating waves. Boss every 5. 120 hull."}
        self.text(88, 653, descriptions[self.mode], 12, VIOLET if self.mode == "endless" else MUTED)
        bob = math.sin(self.animation_clock * 1.1) * 5
        self.oval(745, 164, 440, 440, "#193956", width=1)
        self.oval(792, 211, 346, 346, "#244c67", width=1)
        self.line(960, 155, 960, 204, CYAN)
        self.line(960, 575, 960, 621, CYAN)
        self.sprite("player", 963, 371 + bob, 308)
        self.text(963, 635, "VANGUARD  /  READY FOR DEPLOYMENT", 11, CYAN, "center", True)
        self.text(963, 666, "8 WEAPON LEVELS   /   NOVA BURST   /   AUTO-FIRE", 10, MUTED, "center")
        self.line(88, 714, 1192, 714)
        self.text(88, 739, "WASD / ARROWS  Move     AUTO-FIRE     SPACE / R  Nova     Q  Missile     E  Power-up", 11, MUTED)
        self.text(1192, 739, "F11  FULLSCREEN", 11, MUTED, "ne")
        if self.store.warning:
            self.text(88, 775, self.store.warning, 10, GOLD)

    def draw_projectile(self, bullet):
        x, y = bullet["pos"]
        x, y = FIELD_X + x, FIELD_Y + y
        kind = bullet["kind"]
        vx, vy = bullet["velocity"]
        length = math.hypot(vx, vy) or 1
        dx, dy = vx / length, vy / length
        if kind == "ion":
            self.oval(x - 5, y - 5, 10, 10, RED, "#74284e", 2)
        elif kind in {"missile", "seeker"}:
            radius = 5 if kind == "missile" else 3
            self.line(x - dx * 20, y - dy * 20, x, y, GOLD, 2)
            self.oval(x - radius, y - radius, radius * 2, radius * 2, GOLD, "#fff0b3")
        elif kind in {"lance", "drone", "nova"}:
            color = VIOLET if kind in {"lance", "nova"} else "#70ffd5"
            tail = 29 if kind == "lance" else (13 if kind == "nova" else 10)
            self.line(x - dx * tail, y - dy * tail, x + dx * 4, y + dy * 4, color, 5 if kind == "lance" else 3)
            self.line(x - dx * tail * .7, y - dy * tail * .7, x, y, "#f5edff", 1)
        elif abs(vx) < 24:
            self.sprite("laser" if bullet["owner"] == "player" else "plasma", x, y, 5 if bullet["owner"] == "player" else 6)
        else:
            color = CYAN if bullet["owner"] == "player" else RED
            self.line(x - dx * 15, y - dy * 15, x + dx * 3, y + dy * 3, color, 3)
            self.line(x - dx * 8, y - dy * 8, x, y, "#ecf9ff" if bullet["owner"] == "player" else "#ffcfac", 1)

    def draw_game(self):
        m = self.model
        self.rect(FIELD_X, FIELD_Y, WORLD_WIDTH, WORLD_HEIGHT, "", LINE)
        for sx, sy, speed in self.stars:
            y = (sy + m.elapsed * speed) % WORLD_HEIGHT
            self.line(FIELD_X + sx, FIELD_Y + y, FIELD_X + sx, FIELD_Y + y + 2, "#446078")
        for bullet in m.projectiles:
            x, y = bullet["pos"]
            if not 4 < y < WORLD_HEIGHT - 4 or not 2 < x < WORLD_WIDTH - 2:
                continue
            self.draw_projectile(bullet)
        for pickup in m.pickups:
            x, y = pickup["pos"]
            if 16 < y < WORLD_HEIGHT - 16:
                if pickup["kind"] == "energy":
                    radius = 7 + min(4, pickup.get("value", 1))
                    color = VIOLET
                    self.oval(FIELD_X + x - radius - 4, FIELD_Y + y - radius - 4, 2 * radius + 8, 2 * radius + 8, "#4a3b75")
                    points = [(x, y - radius), (x + radius * .7, y), (x, y + radius), (x - radius * .7, y)]
                    self.canvas.create_polygon(*[v for point in points for v in self.xy(FIELD_X + point[0], FIELD_Y + point[1])],
                                               fill=color, outline="#ede3ff", tags="frame")
                else:
                    self.oval(FIELD_X + x - 23, FIELD_Y + y - 23, 46, 46, POWERUPS[pickup["kind"]]["color"])
                    self.sprite(pickup["kind"], FIELD_X + x, FIELD_Y + y, 34)
        threat = next((e for e in m.threat_order if e in m.enemies), None)
        for enemy in m.enemies:
            x, y = enemy["pos"]
            # The HUD masks below clip ships at the playfield edges.
            margin = 78 if enemy["kind"] == "boss" else 32
            if y < -margin or y > WORLD_HEIGHT + margin:
                continue
            width = {"scout": 57, "heavy": 82, "boss": 244}[enemy["kind"]]
            self.sprite(enemy["kind"], FIELD_X + x, FIELD_Y + y, width)
            if enemy["hp"] < enemy["max_hp"] and enemy["kind"] != "boss":
                self.bar(FIELD_X + x - 24, FIELD_Y + y - 38, 48, enemy["hp"] / enemy["max_hp"], RED, 3)
            if enemy is threat and enemy["kind"] != "boss":
                self.text(FIELD_X + x, FIELD_Y + y - 52, "!", 14, GOLD, "center", True)
            if m.target_clock > 0 and enemy["id"] == m.target_id:
                self.oval(FIELD_X + x - width / 2 - 7, FIELD_Y + y - width / 2 - 7, width + 14, width + 14, GOLD, width=2)
        px, py = m.player["pos"]
        if m.nova_flash > 0:
            radius = (1 - m.nova_flash / .55) * 320 + 15
            self.oval(FIELD_X + px - radius, FIELD_Y + py - radius, radius * 2, radius * 2, VIOLET, width=3)
        if m.weapon_level >= 7:
            for dx, dy in m.drone_positions:
                self.line(FIELD_X + dx, FIELD_Y + dy - 9, FIELD_X + dx, FIELD_Y + dy + 11, VIOLET, 5)
                self.oval(FIELD_X + dx - 6, FIELD_Y + dy - 5, 12, 10, VIOLET, "#1c2a4a", 2)
        if m.player["shield"] > 0:
            self.oval(FIELD_X + px - 47, FIELD_Y + py - 47, 94, 94, CYAN, width=2)
        if m.player["invulnerable"] == 0 or int(m.elapsed * 14) % 2 == 0:
            self.sprite("player", FIELD_X + px, FIELD_Y + py, 60)
        for particle in m.particles:
            x, y = particle["pos"]
            if 3 < x < WORLD_WIDTH - 3 and 3 < y < WORLD_HEIGHT - 3:
                self.rect(FIELD_X + x, FIELD_Y + y, 2.5, 2.5, particle["color"])
        self.text(51, 122, f"{self.name_var.get().upper()}  /  {self.mode.upper()}", 10, MUTED, bold=True)
        if m.multiplier > 1:
            self.text(52, 147, f"x{m.multiplier} COMBO", 20, GOLD, bold=True)
            self.bar(52, 177, 105, m.combo_clock / 4.5, GOLD, 3)
        boss = next((e for e in m.enemies if e["kind"] == "boss"), None)
        if boss:
            self.text(492, 122, "MOTHERSHIP  /  " + ("OVERDRIVE" if boss["hp"] < boss["max_hp"] / 2 else "HOSTILE"), 10, RED, "n", True)
            self.bar(300, 145, 384, boss["hp"] / boss["max_hp"], RED, 5)
        if m.notice_clock > 0:
            self.rect(180, 672, 625, 24, "#0a1728")
            self.text(492, 685, m.notice, 12, CYAN, "center")
        if m.phase in {"briefing", "intermission"}:
            self.rect(252, 298, 480, 143, PANEL, "#315775")
            self.text(492, 327, "SECTOR SECURED" if m.phase == "intermission" else "PREPARE FOR LAUNCH", 12, CYAN, "center", True)
            upcoming = m.wave + 1 if m.phase == "intermission" else m.wave
            self.text(492, 367, f"WAVE {upcoming:02}", 34, INK, "center", True)
            boss_next = upcoming % 5 == 0 if m.mode == "endless" else upcoming == 5
            self.text(492, 411, "MOTHERSHIP INBOUND" if boss_next else "Auto-fire online. Stack energy to evolve.", 13, MUTED, "center")
        # Mask outside the world before drawing the HUD; enemies stay visible
        # until they actually cross a boundary, instead of popping away early.
        self.rect(0, 0, BASE_WIDTH, FIELD_Y, "#080f20")
        self.rect(0, FIELD_Y + WORLD_HEIGHT, BASE_WIDTH, BASE_HEIGHT - FIELD_Y - WORLD_HEIGHT, "#080f20")
        self.rect(0, FIELD_Y, FIELD_X, WORLD_HEIGHT, "#080f20")
        self.rect(FIELD_X + WORLD_WIDTH, FIELD_Y, BASE_WIDTH - FIELD_X - WORLD_WIDTH, WORLD_HEIGHT, "#080f20")
        self.header()
        self.text(420, 24, "SCORE", 10, MUTED, bold=True)
        self.text(420, 43, f"{m.score:06,}", 26 if m.score < 1_000_000 else 20, INK, bold=True)
        self.text(615, 24, "HIGH SCORE", 10, MUTED, bold=True)
        best = max(m.score, self.run_best)
        self.text(615, 43, f"{best:,}", 26 if best < 1_000_000 else 20, GOLD, bold=True)
        self.text(820, 24, "ENDLESS WAVE" if m.mode == "endless" else "MISSION", 10, MUTED, bold=True)
        self.text(820, 45, f"{m.wave:02} / ∞" if m.mode == "endless" else f"{m.wave:02} / 05", 24, VIOLET if m.mode == "endless" else CYAN, bold=True)
        self.button(1080, 29, 168, 39, "PAUSE  [P]", self.toggle_pause, small=True)
        self.draw_sidebar()
        self.text(32, 735, "WASD / ARROWS  Move     AUTO-FIRE     SPACE / R  Nova     Q  Missile     E  Power-up     P / ESC  Pause", 11, MUTED)
        self.text(1248, 735, "F11  FULLSCREEN", 11, MUTED, "ne")
        self.text(32, 770, f"FLIGHT TIME  {int(m.elapsed) // 60:02}:{int(m.elapsed) % 60:02}     HOSTILES DESTROYED  {m.kills:02}", 10, "#647f9f")
        if self.audio.available:
            self.text(1248, 770, "M  SOUND " + ("ON" if self.audio.enabled else "OFF"), 10, MUTED, "ne")

    def draw_sidebar(self):
        m = self.model
        self.rect(980, 105, 268, 110, PANEL, LINE)
        self.text(1000, 118, "HULL INTEGRITY", 10, MUTED, bold=True)
        hp, total = m.player["health"], m.player["max_health"]
        color = CYAN if hp > total * .35 else RED
        self.text(1000, 140, f"{int(hp):03}", 29, color, bold=True)
        self.text(1074, 153, f"/ {total}", 13, MUTED)
        self.bar(1000, 181, 228, hp / total, color, 6)
        timers = []
        if m.player["shield"] > 0:
            timers.append(f"SHIELD {m.player['shield']:.0f}s")
        if m.player["rapid_fire"] > 0:
            timers.append(f"RAPID {m.player['rapid_fire']:.0f}s")
        self.text(1000, 197, "  /  ".join(timers) or "SYSTEMS OPERATIONAL", 9, CYAN if timers else MUTED)

        self.rect(980, 227, 268, 180, PANEL, "#51416d")
        self.text(1000, 240, "ENERGY CORE", 10, VIOLET, bold=True)
        self.text(1228, 240, f"LV {m.weapon_level} / 8", 11, VIOLET, "ne", True)
        self.text(1000, 261, m.weapon["name"], 21, INK, bold=True)
        self.text(1228, 271, f"{m.energy} E", 12, VIOLET, "ne", True)
        for index in range(8):
            self.rect(1000 + index * 29, 295, 25, 4, VIOLET if index < m.weapon_level else "#24324a")
        self.text(1000, 309, f"{m.volley_size} shots / salvo  |  {1 / m.fire_interval:.1f} salvos/s", 10, MUTED)
        next_spec = WEAPON_TIERS[m.weapon_level] if m.weapon_level < 8 else None
        hint = f"NEXT: {next_spec['name']} at {next_spec['energy']} energy" if next_spec else "MAX CORE  /  Energy still charges Nova"
        self.text(1000, 330, hint, 9, VIOLET)
        ready = m.nova_charge >= 100
        self.text(1000, 356, "SPACE / R  NOVA BURST", 10, INK, bold=True)
        self.text(1228, 356, "READY" if ready else f"{m.nova_charge}%", 10, VIOLET, "ne", True)
        self.bar(1000, 380, 228, m.nova_charge / 100, VIOLET, 6)

        self.rect(980, 419, 268, 138, PANEL, LINE)
        self.text(1000, 431, "POWER-UP RESERVE", 10, MUTED, bold=True)
        self.text(1228, 431, f"{len(m.inventory)} / 4", 10, CYAN, "ne")
        next_index = m.next_powerup_index()
        for i in range(4):
            x = 1000 + i * 58
            self.rect(x, 455, 50, 53, "#112039", CYAN if i == next_index else LINE)
            if i < len(m.inventory):
                item = m.inventory[i]
                self.sprite(item["kind"], x + 25, 475, 29)
                label = {"repair": "REPAIR", "shield": "SHIELD", "rapid_fire": "RAPID"}[item["kind"]]
                self.text(x + 25, 497, label, 8, item["color"], "center", True)
            else:
                self.text(x + 25, 481, "+", 17, "#36506f", "center")
        label = m.inventory[next_index]["label"] if next_index is not None else "Awaiting pickup"
        self.text(1000, 520, f"E  {label}", 11, CYAN, bold=True)
        self.text(1000, 541, f"DISCOVERED {len(m.unique_powerups)} / 3", 8, MUTED)
        for i, kind in enumerate(("shield", "repair", "rapid_fire")):
            self.oval(1178 + i * 18, 540, 8, 8, POWERUPS[kind]["color"] if kind in m.unique_powerups else LINE,
                      POWERUPS[kind]["color"] if kind in m.unique_powerups else "")

        self.rect(980, 569, 268, 74, PANEL, LINE)
        self.text(1000, 581, "TOP THREAT", 10, MUTED, bold=True)
        alive = [e for e in m.threat_order if e in m.enemies]
        if alive:
            enemy = alive[0]
            self.sprite(enemy["kind"], 1015, 617, 25)
            self.text(1040, 608, enemy["kind"].upper(), 11, INK, bold=True)
            self.text(1228, 608, str(enemy["threat"]), 12, GOLD, "ne", True)
            self.bar(1040, 629, 188, enemy["threat"] / 150, GOLD, 3)
        else:
            self.text(1000, 610, "Scanning the perimeter...", 11, MUTED)
        self.rect(980, 655, 268, 50, PANEL, LINE)
        self.text(1000, 667, "Q  HOMING MISSILE", 10, INK, bold=True)
        self.text(1228, 667, f"{m.missile_cooldown:.1f}s" if m.missile_cooldown else "READY", 10, GOLD, "ne", True)
        self.bar(1000, 692, 228, 1 - m.missile_cooldown / 5, GOLD, 4)

    def draw_pause(self):
        self.rect(0, 0, BASE_WIDTH, BASE_HEIGHT, "#030713", stipple="gray50")
        self.rect(400, 220, 480, 353, PANEL, "#3d607b")
        self.text(640, 264, "FLIGHT PAUSED", 28, INK, "center", True)
        self.text(640, 306, "Your ship is safe. Resume when ready.", 14, MUTED, "center")
        # Underlying game buttons must not receive clicks through this overlay.
        self.buttons.clear()
        self.button(462, 354, 356, 52, "RESUME MISSION", self.toggle_pause, primary=True)
        self.button(462, 426, 356, 48, "END RUN & SAVE SCORE", self.end_run)
        self.text(640, 525, "P / ESC to resume", 12, MUTED, "center")

    def draw_result(self):
        m = self.model
        victory = m.status == "victory"
        self.text(640, 139, "MISSION COMPLETE" if victory else "FLIGHT ENDED", 12, CYAN if victory else RED, "center", True)
        self.text(640, 194, "GALAXY SECURED" if victory else "A NEW FLIGHT AWAITS", 39, INK, "center", True)
        subtitle = (f"ENDLESS / {m.waves_cleared} waves cleared. Return stronger." if m.mode == "endless" else
                    "The mothership has fallen. Your sector is safe." if victory else
                    "Collect energy, charge your Nova, and try again.")
        self.text(640, 244, subtitle, 15, MUTED, "center")
        self.rect(290, 291, 700, 136, PANEL, "#35556e")
        self.text(640, 315, "NEW HIGH SCORE" if self.new_best else "FINAL SCORE", 12, GOLD if self.new_best else MUTED, "center", True)
        self.text(640, 369, f"{m.score:,}", 52, CYAN, "center", True)
        stats = [("WAVE REACHED", str(m.wave) if m.mode == "endless" else f"{m.wave} / 5"),
                 ("ENERGY", str(m.energy)), ("CORE LEVEL", f"{m.weapon_level} / 8"),
                 ("DESTROYED", str(m.kills)), ("FLIGHT TIME", f"{int(m.elapsed)//60:02}:{int(m.elapsed)%60:02}")]
        for i, (label, value) in enumerate(stats):
            x = 310 + i * 165
            self.text(x, 468, label, 11, MUTED, "center", True)
            self.text(x, 503, value, 24, INK, "center", True)
        self.text(640, 555, f"{self.name_var.get()}  /  {m.mode.upper()}  /  BEST {self.store.best(m.mode):,}", 12, MUTED, "center")
        self.button(290, 603, 330, 54, "FLY AGAIN", self.start_game, primary=True)
        self.button(660, 603, 330, 54, "MAIN MENU", lambda: self.show("menu"))
        self.text(640, 709, self.store.warning or "Score saved locally. Your next mission is waiting.", 12,
                  GOLD if self.store.warning else MUTED, "center")

    def draw_leaderboard(self):
        self.text(88, 120, "PILOT HALL OF FAME", 34, INK, bold=True)
        self.text(88, 171, "Your ten best local runs. Each flight mode has its own board.", 14, MUTED)
        for mode, x in (("standard", 800), ("relaxed", 930), ("endless", 1060)):
            self.button(x, 130, 120, 40, mode.upper(), lambda m=mode: self.select_mode(m), self.mode == mode, small=True)
        self.rect(88, 218, 1104, 48, "#12243b")
        for x, label in ((108, "RANK"), (215, "PILOT"), (640, "SCORE"), (810, "WAVE"), (920, "RESULT"), (1080, "DATE")):
            self.text(x, 235, label, 11, MUTED, bold=True)
        records = self.store.records[self.mode]
        for i, record in enumerate(records):
            y = 275 + i * 37
            self.rect(88, y, 1104, 35, "#0c1b2d" if i % 2 == 0 else "#0a1627")
            color = GOLD if i == 0 else INK
            self.text(108, y + 9, f"{i + 1:02}", 13, color, bold=True)
            self.text(215, y + 9, record["name"], 13, INK)
            self.text(640, y + 9, f"{record['score']:,}", 13, color, bold=True)
            self.text(810, y + 9, str(record.get("wave", 0) or "—"), 12, MUTED)
            self.text(920, y + 9, "CLEARED" if record["result"] == "victory" else "ENDED", 11, MUTED)
            self.text(1080, y + 9, record["date"], 11, MUTED)
        if not records:
            self.text(640, 426, "No flights recorded yet.", 24, INK, "center", True)
            self.text(640, 470, "Launch a mission to set the first high score.", 15, MUTED, "center")
        self.button(88, 708, 235, 46, "BACK TO MENU", lambda: self.show("menu"))

    def draw_instructions(self):
        self.text(64, 119, "FLIGHT MANUAL", 34, INK, bold=True)
        self.text(64, 167, "Choose a five-wave mission or survive the Endless fleet. Evolve your weapons in every mode.", 14, MUTED)
        self.rect(64, 210, 550, 451, PANEL, LINE)
        self.rect(638, 210, 578, 451, PANEL, LINE)
        self.text(88, 231, "YOUR CONTROLS", 12, CYAN, bold=True)
        controls = [("WASD / ARROWS", "Move your ship"), ("AUTO-FIRE", "Your weapons fire during combat"),
                    ("SPACE / R", "Nova Burst when charge reaches 100%"),
                    ("Q", "Launch a homing missile (5s cooldown)"), ("E", "Use the next usable power-up"),
                    ("P / ESC", "Pause or resume"), ("F11", "Toggle fullscreen")]
        for i, (key, action) in enumerate(controls):
            y = 273 + i * 42
            self.text(88, y, key, 11, INK, bold=True)
            self.text(247, y, action, 13, MUTED)
        self.text(88, 594, "Switching away from the window pauses play.\nEnding a run saves its score.", 12, MUTED, width=490)
        self.text(662, 231, "SURVIVE. COLLECT. DEFEND.", 12, CYAN, bold=True)
        paragraphs = [
            "Standard and Relaxed end after wave five. Endless keeps going, with stronger enemies and a boss every five waves. Zero hull ends your run.",
            "Collect violet energy crystals. Energy stacks for the whole run, adding barrels, firing speed, lances, drones and seekers. Open ARSENAL for all eight tiers.",
            "Each energy unit adds 10% Nova charge. SPACE or R releases 24 radial bolts, clears hostile bullets and grants 1 second of protection. Weapon levels stay intact.",
            "Every third kill drops a reserve pickup. Press E: repair +35 hull, shield 6s, or rapid fire 8s with two extra barrels. Full hull saves repair for later.",
            "Q targets the most valuable enemy and deals splash damage. Quick kills increase your multiplier. Discover all three reserve types for +300 points.",
            "Nearby energy moves toward your ship. Between waves it is pulled from across the field. Endless restores 6 hull per clear, or 15 after a boss wave.",
        ]
        for i, paragraph in enumerate(paragraphs):
            self.text(662, 273 + i * 62, paragraph, 12, INK if i == 0 else MUTED, width=520)
        self.button(64, 708, 210, 46, "BACK TO MENU", lambda: self.show("menu"))
        self.button(298, 708, 240, 46, "COURSE CONCEPTS", lambda: self.show("concepts"))
        self.button(562, 708, 210, 46, "ARSENAL", lambda: self.show("arsenal"))
        self.button(926, 708, 290, 46, "LAUNCH MISSION", self.start_game, primary=True)

    def draw_arsenal(self):
        self.text(64, 119, "EVOLVE YOUR ARSENAL", 32, INK, bold=True)
        self.text(64, 166, "Collect violet crystals. Your upgrades last until the run ends, even after taking damage or using Nova.", 13, MUTED)
        self.rect(64, 212, 1152, 43, "#19233d", "#51416d")
        for x, label in ((84, "LEVEL"), (185, "ENERGY"), (300, "CORE"), (505, "SHOTS"), (620, "SALVOS / S"), (795, "UNLOCK")):
            self.text(x, 226, label, 10, VIOLET, bold=True)
        for index, spec in enumerate(WEAPON_TIERS):
            y = 263 + index * 45
            self.rect(64, y, 1152, 42, "#0b182b" if index % 2 == 0 else "#102036")
            shots = spec["lanes"] + (2 if index >= 6 else 0)
            for x, value, color in ((84, f"{index + 1:02}", VIOLET), (185, str(spec["energy"]), INK),
                                    (300, spec["name"], INK), (505, str(shots), CYAN),
                                    (620, f"{1 / spec['interval']:.1f}", CYAN), (795, spec["unlock"], MUTED)):
                self.text(x, y + 13, value, 12, color, bold=x == 300)
        self.text(64, 644, "Rapid fire: +2 barrels and faster salvos. TEMPEST also launches two homing bolts every 1.6s when a target is visible.", 12, MUTED)
        self.text(64, 670, "At maximum level, additional energy keeps scoring and recharging Nova. Energy and upgrades reset only for a new run.", 12, VIOLET)
        self.button(64, 708, 250, 46, "BACK TO MANUAL", lambda: self.show("instructions"))

    def draw_concepts(self):
        self.text(64, 119, "PROJECT NOTES", 34, INK, bold=True)
        self.text(64, 168, "All seven course concepts support a real game feature. See docs/FEATURE_MAP.md for code locations and traces.", 14, MUTED)
        rows = [
            ("BUBBLE SORT", "Threat radar ranks living enemies; the leading threat receives a warning marker."),
            ("INSERTION SORT", "Collected power-ups enter a priority-ordered reserve. It also maintains the score board."),
            ("SELECTION SORT", "Homing missiles rank remaining targets by point value and choose the best target."),
            ("TUPLES", "Ships, projectiles, pickups, and formation offsets use (x, y) coordinate pairs."),
            ("SETS", "Unique pickup discoveries give a one-time bonus; all three types unlock +300 points."),
            ("DICTIONARIES", "Named player and enemy stats store health, damage, speed, threat, and score value."),
            ("RECURSION", "Nested wave groups expand into timed spawns. Enemy leaves and empty groups stop recursion."),
        ]
        for i, (title, detail) in enumerate(rows):
            y = 222 + i * 62
            self.rect(64, y, 1152, 53, PANEL, LINE)
            self.text(84, y + 18, title, 11, CYAN, bold=True)
            self.text(270, y + 17, detail, 13, INK, width=920)
        self.button(64, 708, 250, 46, "BACK TO MANUAL", lambda: self.show("instructions"))
