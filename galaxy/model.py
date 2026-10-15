"""Display-independent game rules. No Tk widgets, file access, or recursion loop."""

import math
import random
from .algorithms import bubble_sort, insert_ordered, insertion_sort, selection_sort
from .formations import WORLD_WIDTH as WIDTH, WORLD_HEIGHT as HEIGHT, WAVE_COUNT, wave_tree, endless_wave_tree, expand_formation
from .weapons import WEAPON_TIERS, tier_for_energy, spread_angles, MAX_PLAYER_PROJECTILES, MAX_ENEMY_PROJECTILES, MAX_PICKUPS

ENEMY_STATS = {
    "scout": {"hp": 36, "damage": 12, "value": 100, "speed": 58, "radius": 23, "threat": 20},
    "heavy": {"hp": 108, "damage": 19, "value": 260, "speed": 30, "radius": 34, "threat": 65},
    "boss": {"hp": 1250, "damage": 16, "value": 2400, "speed": 48, "radius": 88, "threat": 100},
}
POWERUPS = {
    "repair": {"label": "Hull repair", "priority": 30, "color": "#6ff59a"},
    "shield": {"label": "Shield", "priority": 20, "color": "#52dcff"},
    "rapid_fire": {"label": "Rapid fire", "priority": 10, "color": "#ffc56b"},
}


def distance(a: tuple, b: tuple) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def segment_hits_circle(start: tuple, end: tuple, center: tuple, radius: float) -> bool:
    """Swept collision prevents a fast laser from jumping over a small ship."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    length_sq = dx * dx + dy * dy
    t = 0 if length_sq == 0 else max(0, min(1, ((center[0] - start[0]) * dx +
                                               (center[1] - start[1]) * dy) / length_sq))
    return distance((start[0] + dx * t, start[1] + dy * t), center) <= radius


class GameModel:
    def __init__(self, mode: str = "standard", seed: int | None = None):
        if mode not in {"standard", "relaxed", "endless"}:
            raise ValueError("Unknown difficulty")
        self.mode = mode
        self.rng = random.Random(seed)
        health = 150 if mode == "relaxed" else (120 if mode == "endless" else 100)
        # DICTIONARY: mutable named player stats; TUPLE: fixed coordinate pair.
        self.player = {"pos": (WIDTH / 2, HEIGHT - 70), "health": health,
                       "max_health": health, "damage": 18, "speed": 340,
                       "shield": 0.0, "rapid_fire": 0.0, "invulnerable": 0.0}
        self.enemies = []
        self.projectiles = []
        self.pickups = []
        self.particles = []
        self.inventory = []
        self.unique_powerups = set()  # SET: first discovery earns a bonus once.
        self.energy = 0
        self.nova_charge = 0
        self.nova_flash = 0.0
        self.seeker_clock = 0.0
        self.volleys = 0
        self.waves_cleared = 0
        self.events = []
        self.status = "playing"
        self.phase = "briefing"
        self.wave = 1
        self.wave_clock = 0.0
        self.phase_clock = 2.0
        self.elapsed = 0.0
        self.score = 0
        self.kills = 0
        self.shots_fired = 0
        self.shots_hit = 0
        self.streak = 0
        self.combo_clock = 0.0
        self.fire_clock = 0.0
        self.missile_cooldown = 0.0
        self.target_id = None
        self.target_clock = 0.0
        self.last_target_value = 0
        self.radar_clock = 0.0
        self.threat_order = []
        self.next_id = 1
        self.notice = "Survive. Stack energy. Boss every 5 waves." if mode == "endless" else "Auto-fire online. Collect energy to evolve your weapons."
        self.notice_clock = 3.0
        self.pickup_cycle = 0
        self.wave_spawn_total = 0
        self.spawn_queue = []
        self._prepare_wave()

    @property
    def multiplier(self):
        return min(4, 1 + self.streak // 4)

    @property
    def accuracy(self):
        return round(100 * self.shots_hit / self.shots_fired) if self.shots_fired else 0

    @property
    def weapon_tier(self):
        return tier_for_energy(self.energy)

    @property
    def weapon_level(self):
        return self.weapon_tier + 1

    @property
    def weapon(self):
        return WEAPON_TIERS[self.weapon_tier]

    @property
    def fire_interval(self):
        return self.weapon["interval"] * (.62 if self.player["rapid_fire"] > 0 else 1)

    @property
    def volley_size(self):
        return self.weapon["lanes"] + (2 if self.player["rapid_fire"] > 0 else 0) + (2 if self.weapon_level >= 7 else 0)

    @property
    def drone_positions(self):
        x, y = self.player["pos"]
        return tuple((max(12, min(WIDTH - 12, x + side * 46)),
                      min(HEIGHT - 12, y + 9 + math.sin(self.elapsed * 3 + side) * 9))
                     for side in (-1, 1))

    def say(self, message: str, duration: float = 2.2):
        self.notice, self.notice_clock = message, duration

    def _prepare_wave(self):
        # RECURSION: actual nested wave -> actual timed enemy spawn queue.
        tree = endless_wave_tree(self.wave) if self.mode == "endless" else wave_tree(self.wave)
        spawns = expand_formation(tree)
        self.spawn_queue = insertion_sort(spawns, key=lambda s: s["time"])
        self.wave_spawn_total = len(self.spawn_queue)
        self.wave_clock = 0.0

    def spawn_enemy(self, kind: str, position: tuple) -> dict:
        stats = ENEMY_STATS[kind]
        enemy = dict(stats)
        if self.mode == "endless":
            growth = self.wave - 1
            hp_scale = 1 + .14 * growth + .012 * growth * growth
            if kind == "boss":
                hp_scale *= 1 + .06 * self.wave
            enemy["hp"] = round(stats["hp"] * hp_scale)
            enemy["damage"] = round(stats["damage"] * (1 + min(1.5, growth * .035)))
            enemy["value"] = round(stats["value"] * (1 + growth * .05))
        enemy.update({"id": self.next_id, "kind": kind, "pos": tuple(position),
                      "max_hp": enemy["hp"], "age": 0.0, "anchor_x": position[0],
                      "fire_clock": self.rng.uniform(1.2, 2.8),
                      "phase": self.rng.uniform(0, math.tau), "salvos": 0})
        self.next_id += 1
        self.enemies.append(enemy)
        return enemy

    def update_threat_ranking(self):
        for enemy in self.enemies:
            closeness = max(0, 1 - distance(enemy["pos"], self.player["pos"]) / HEIGHT)
            enemy["threat"] = round(ENEMY_STATS[enemy["kind"]]["threat"] + closeness * 45)
        # BUBBLE SORT: drives the visible radar and the danger marker.
        visible = [e for e in self.enemies if 0 < e["pos"][1] < HEIGHT]
        self.threat_order = bubble_sort(visible, key=lambda e: e["threat"], reverse=True)

    def choose_target(self) -> dict | None:
        visible = [e for e in self.enemies if 0 < e["pos"][1] < HEIGHT and e["hp"] > 0]
        # SELECTION SORT: repeated largest-remaining selection, not max().
        ranked = selection_sort(visible, key=lambda e: e["value"], reverse=True)
        return ranked[0] if ranked else None

    def launch_missile(self) -> bool:
        if self.status != "playing" or self.phase != "combat" or self.missile_cooldown > 0:
            return False
        target = self.choose_target()
        if not target:
            self.say("No target in range.")
            return False
        x, y = self.player["pos"]
        if not self._player_bullet("missile", (x, y - 28), (0, -490), 110,
                                   life=4.0, target_id=target["id"]):
            return False
        self.target_id, self.target_clock = target["id"], 2.0
        self.last_target_value = target["value"]
        self.missile_cooldown = 5.0
        self.events.append("missile")
        self.say(f"Locked: {target['kind'].upper()} / {target['value']} points")
        return True

    def collect_energy(self, amount: int = 1) -> bool:
        """Energy persists for this run; Nova uses charge, never weapon energy."""
        if self.status != "playing" or type(amount) is not int or amount <= 0:
            return False
        old_level = self.weapon_level
        was_ready = self.nova_charge >= 100
        self.energy += amount
        self.nova_charge = min(100, self.nova_charge + 10 * amount)
        self.score += 10 * amount
        if self.weapon_level > old_level:
            self.say(f"WEAPON LEVEL {self.weapon_level}: {self.weapon['name']} / {self.weapon['unlock']}", 3)
            self.burst(self.player["pos"], "#b493ff", 22)
            self.events.append("powerup")
        elif not was_ready and self.nova_charge >= 100:
            self.say("NOVA READY - Press SPACE or R to release a radial burst!", 2.5)
        return True

    def _player_bullet(self, kind, position, velocity, damage, life=2.0,
                       pierce=1, target_id=None):
        if sum(b["owner"] == "player" for b in self.projectiles) >= MAX_PLAYER_PROJECTILES:
            return False
        self.projectiles.append({"owner": "player", "kind": kind, "pos": tuple(position),
                                 "velocity": tuple(velocity), "damage": damage, "life": life,
                                 "pierce": pierce, "hit_ids": set(), "counted_hit": False,
                                 "target_id": target_id})
        self.shots_fired += 1
        return True

    def launch_nova(self) -> bool:
        if self.status != "playing" or self.phase != "combat" or self.nova_charge < 100:
            return False
        self.nova_charge = 0
        self.nova_flash = .55
        self.projectiles = [b for b in self.projectiles if b["owner"] == "player"]
        for index in range(24):
            angle = index * math.tau / 24
            self._player_bullet("nova", self.player["pos"],
                                (math.cos(angle) * 470, math.sin(angle) * 470),
                                48 + self.weapon_level * 4, life=1.8, pierce=2)
        self.player["invulnerable"] = max(1.0, self.player["invulnerable"])
        self.burst(self.player["pos"], "#b493ff", 30)
        self.events.append("missile")
        self.say("NOVA BURST! Hostile projectiles cleared.")
        return True

    def collect_powerup(self, kind: str) -> bool:
        if kind not in POWERUPS:
            raise ValueError("Unknown power-up")
        if len(self.inventory) >= 4:
            self.say("Reserve full. Press E to use a power-up.", 1)
            return False
        item = {"kind": kind, **POWERUPS[kind]}
        # INSERTION SORT: the list was already ordered; shift and insert one item.
        self.inventory = insert_ordered(self.inventory, item,
                                        key=lambda p: p["priority"], reverse=True)
        first = kind not in self.unique_powerups
        self.unique_powerups.add(kind)
        self.score += 60 if first else 20
        if first and len(self.unique_powerups) == 3:
            self.score += 300
            self.say("Collection complete! +300 points", 3)
        else:
            self.say(f"{POWERUPS[kind]['label']} collected. Press E to activate.")
        self.events.append("pickup")
        return True

    def next_powerup_index(self) -> int | None:
        for index, item in enumerate(self.inventory):
            if item["kind"] != "repair" or self.player["health"] < self.player["max_health"]:
                return index
        return None

    def activate_powerup(self) -> bool:
        if self.status != "playing":
            return False
        index = self.next_powerup_index()
        if index is None:
            self.say("Hull is full; repair saved for later." if self.inventory else "Collect a power-up first.")
            return False
        item = self.inventory.pop(index)
        kind = item["kind"]
        if kind == "repair":
            self.player["health"] = min(self.player["max_health"], self.player["health"] + 35)
        elif kind == "shield":
            self.player["shield"] = min(12, self.player["shield"] + 6)
        else:
            self.player["rapid_fire"] = min(16, self.player["rapid_fire"] + 8)
        self.events.append("powerup")
        self.say(f"{item['label']} activated!")
        self.burst(self.player["pos"], item["color"], 16)
        return True

    def fire(self):
        if self.status != "playing" or self.fire_clock > 0 or self.phase != "combat":
            return
        rapid = self.player["rapid_fire"] > 0
        self.fire_clock = self.fire_interval
        self.volleys += 1
        x, y = self.player["pos"]
        count = self.weapon["lanes"] + (2 if rapid else 0)
        speed = self.weapon["speed"]
        for index, angle in enumerate(spread_angles(count)):
            lance = self.weapon_level >= 6 and self.volleys % 3 == 0 and index == count // 2
            self._player_bullet("lance" if lance else "laser",
                                (max(5, min(WIDTH - 5, x + (index - (count - 1) / 2) * 7)), y - 34),
                                (math.sin(angle) * speed, -math.cos(angle) * speed),
                                (32 if lance else self.player["damage"]) + self.weapon_tier,
                                pierce=3 if lance else 1)
        if self.weapon_level >= 7:
            for position in self.drone_positions:
                self._player_bullet("drone", position, (0, -760), 14 + self.weapon_tier)
        if self.weapon_level >= 8 and self.seeker_clock <= 0:
            target = self.choose_target()
            if target:
                self.seeker_clock = 1.6
                for side in (-1, 1):
                    self._player_bullet("seeker", (x + side * 22, y - 20), (side * 160, -460),
                                        28, life=3.0, target_id=target["id"])
        self.events.append("shoot")

    def burst(self, pos: tuple, color: str, count: int = 10):
        for _ in range(count):
            angle, speed = self.rng.uniform(0, math.tau), self.rng.uniform(35, 170)
            self.particles.append({"pos": pos, "velocity": (math.cos(angle) * speed, math.sin(angle) * speed),
                                   "life": self.rng.uniform(.2, .65), "color": color})
        self.particles = self.particles[-160:]

    def damage_player(self, damage: float, breach: bool = False):
        if self.status != "playing":
            return
        if not breach and (self.player["invulnerable"] > 0 or self.player["shield"] > 0):
            return
        scale = .7 if self.mode == "relaxed" else 1.0
        self.player["health"] = max(0, self.player["health"] - round(damage * scale))
        self.player["invulnerable"] = 1.0
        self.streak, self.combo_clock = 0, 0
        self.events.append("hit")
        self.burst(self.player["pos"], "#ff6b84", 12)
        if self.player["health"] <= 0:
            self.finish("defeat")

    def damage_enemy(self, enemy: dict, damage: float):
        if enemy not in self.enemies or self.status != "playing":
            return
        enemy["hp"] -= damage
        self.burst(enemy["pos"], "#ffc56b", 3)
        if enemy["hp"] > 0:
            return
        self.enemies.remove(enemy)
        self.streak += 1
        self.combo_clock = 4.5
        self.score += enemy["value"] * self.multiplier
        self.kills += 1
        self.events.append("explosion")
        self.burst(enemy["pos"], "#ffb66c", 25 if enemy["kind"] == "boss" else 13)
        self.pickups.append({"kind": "energy", "pos": enemy["pos"], "age": 0,
                             "value": {"scout": 1, "heavy": 2, "boss": 6}[enemy["kind"]]})
        if enemy["kind"] == "boss":
            self.projectiles = [b for b in self.projectiles if b["owner"] == "player"]
            self.say("Mothership destroyed. Clear any remaining escorts!", 3)
        if self.kills % 3 == 0:
            kind = ("shield", "rapid_fire", "repair")[self.pickup_cycle % 3]
            self.pickup_cycle += 1
            self.pickups.append({"kind": kind, "pos": enemy["pos"], "age": 0})
        self.pickups = self.pickups[-MAX_PICKUPS:]

    def finish(self, result: str):
        if self.status not in {"playing", "paused"}:
            return
        if result not in {"victory", "defeat"}:
            raise ValueError("Unknown result")
        if result == "victory":
            self.score += 1000 + int(self.player["health"]) * 10
        self.status = result
        self.events.append(result)

    def _enemy_fire(self, enemy: dict):
        x, y = enemy["pos"]
        px, py = self.player["pos"]
        angle = math.atan2(py - y, px - x)
        enemy["salvos"] += 1
        offsets = (0,)
        if enemy["kind"] == "heavy":
            offsets = (-.12, .12)
        elif enemy["kind"] == "boss":
            offsets = (-.55, -.28, 0, .28, .55) if enemy["hp"] > enemy["max_hp"] / 2 else (-.72, -.48, -.24, 0, .24, .48, .72)
        speed = (175 if enemy["kind"] == "boss" else 160) * (.8 if self.mode == "relaxed" else 1)
        if self.mode == "endless":
            speed *= 1 + min(.65, (self.wave - 1) * .025)
        angles = tuple(angle + offset for offset in offsets)
        kind = "plasma"
        if enemy["kind"] == "boss" and enemy["salvos"] % 3 == 0:
            # Slow rings alternate with aimed fans, leaving readable dodge gaps.
            angles = tuple(i * math.tau / 14 + enemy["age"] * .25 for i in range(14))
            speed *= .72
            kind = "ion"
        available = MAX_ENEMY_PROJECTILES - sum(b["owner"] == "enemy" for b in self.projectiles)
        for direction in angles[:max(0, available)]:
            self.projectiles.append({"owner": "enemy", "kind": kind, "pos": (x, y + 24),
                                     "velocity": (math.cos(direction) * speed, math.sin(direction) * speed),
                                     "damage": enemy["damage"], "life": 7.0})

    def _move_enemies(self, dt: float):
        for enemy in self.enemies[:]:
            enemy["age"] += dt
            x, y = enemy["pos"]
            if enemy["kind"] == "boss":
                y = min(112, y + 65 * dt)
                x = WIDTH / 2 + math.sin(enemy["age"] * .65) * 235
            else:
                y += enemy["speed"] * (1 + min(1.0, (self.wave - 1) * .06)) * dt
                x = enemy["anchor_x"] + math.sin(enemy["age"] * 1.7 + enemy["phase"]) * 48
            enemy["pos"] = (max(40, min(WIDTH - 40, x)), y)
            enemy["fire_clock"] -= dt
            if enemy["fire_clock"] <= 0 and 30 < y < HEIGHT - 100:
                self._enemy_fire(enemy)
                enemy["fire_clock"] = (1.25 if enemy["kind"] == "boss" else self.rng.uniform(2.0, 3.5))
                if enemy["kind"] == "boss" and enemy["hp"] < enemy["max_hp"] / 2:
                    enemy["fire_clock"] = .86
                if self.mode == "endless":
                    enemy["fire_clock"] /= 1 + min(1.0, (self.wave - 1) * .03)
            if y > HEIGHT + 60:
                self.enemies.remove(enemy)
                self.damage_player(14 if enemy["kind"] == "heavy" else 9, breach=True)
                self.say("Enemy breached the perimeter. Hull damaged.")
            elif distance(enemy["pos"], self.player["pos"]) < enemy["radius"] + 18:
                self.damage_player(26)
                if enemy["kind"] != "boss":
                    self.enemies.remove(enemy)
                    self.burst(enemy["pos"], "#ffb66c", 10)
            if self.status != "playing":
                break

    def _move_projectiles(self, dt: float):
        # Build a survivor list; never remove bullets from the active iterator.
        survivors = []
        boss_destroyed = False
        for bullet in self.projectiles[:]:
            if self.status != "playing":
                break
            old = bullet["pos"]
            if bullet["kind"] in {"missile", "seeker"}:
                target = next((e for e in self.enemies if e["id"] == bullet["target_id"]), None)
                if target is None:
                    target = self.choose_target()
                    if target:
                        bullet["target_id"] = target["id"]
                if target:
                    dx, dy = target["pos"][0] - old[0], target["pos"][1] - old[1]
                    length = math.hypot(dx, dy) or 1
                    speed = 520 if bullet["kind"] == "missile" else 600
                    bullet["velocity"] = (dx / length * speed, dy / length * speed)
            vx, vy = bullet["velocity"]
            new = (old[0] + vx * dt, old[1] + vy * dt)
            bullet["pos"], bullet["life"] = new, bullet["life"] - dt
            hit = False
            if bullet["owner"] == "player":
                hit_ids = bullet.setdefault("hit_ids", set())
                for enemy in self.enemies[:]:
                    if enemy["id"] not in hit_ids and segment_hits_circle(old, new, enemy["pos"], enemy["radius"] + 4):
                        hit_ids.add(enemy["id"])
                        if not bullet.get("counted_hit", False):
                            self.shots_hit += 1
                            bullet["counted_hit"] = True
                        was_boss = enemy["kind"] == "boss"
                        self.damage_enemy(enemy, bullet["damage"])
                        boss_destroyed = boss_destroyed or (was_boss and enemy["hp"] <= 0)
                        if bullet["kind"] == "missile":
                            for nearby in self.enemies[:]:
                                if nearby is not enemy and distance(nearby["pos"], new) < 90:
                                    self.damage_enemy(nearby, 60)
                                    boss_destroyed = boss_destroyed or (nearby["kind"] == "boss" and nearby["hp"] <= 0)
                            self.burst(new, "#ffc56b", 24)
                        bullet["pierce"] = bullet.get("pierce", 1) - 1
                        if bullet["pierce"] <= 0:
                            hit = True
                            break
            elif not boss_destroyed and segment_hits_circle(old, new, self.player["pos"], 21):
                self.damage_player(bullet["damage"])
                hit = True
            if not hit and bullet["life"] > 0 and -80 < new[0] < WIDTH + 80 and -80 < new[1] < HEIGHT + 80:
                survivors.append(bullet)
        self.projectiles = [b for b in survivors if not boss_destroyed or b["owner"] == "player"]

    def step(self, dt: float, keys: set[str]):
        """One bounded update, called by Tk.after. Never calls itself."""
        if self.status != "playing":
            return
        dt = max(0.0, min(.05, dt))
        self.elapsed += dt
        for name in ("fire_clock", "missile_cooldown", "target_clock", "notice_clock", "combo_clock", "seeker_clock", "nova_flash"):
            setattr(self, name, max(0, getattr(self, name) - dt))
        if self.combo_clock == 0:
            self.streak = 0
        for name in ("shield", "rapid_fire", "invulnerable"):
            self.player[name] = max(0, self.player[name] - dt)
        dx = int(bool(keys & {"d", "right"})) - int(bool(keys & {"a", "left"}))
        dy = int(bool(keys & {"s", "down"})) - int(bool(keys & {"w", "up"}))
        length = math.hypot(dx, dy) or 1
        x, y = self.player["pos"]
        self.player["pos"] = (max(30, min(WIDTH - 30, x + dx / length * self.player["speed"] * dt)),
                              max(50, min(HEIGHT - 30, y + dy / length * self.player["speed"] * dt)))
        if self.phase != "combat":
            self.phase_clock -= dt
            if self.phase_clock <= 0:
                if self.phase == "intermission":
                    self.wave += 1
                    self._prepare_wave()
                self.phase = "combat"
        if self.phase == "combat":
            self.wave_clock += dt
            while self.spawn_queue and self.spawn_queue[0]["time"] <= self.wave_clock:
                spawn = self.spawn_queue.pop(0)
                self.spawn_enemy(spawn["kind"], spawn["pos"])
            self.fire()  # Automatic fire in every mode; Space/R now releases Nova.
            self._move_enemies(dt)
            if self.status == "playing":
                self._move_projectiles(dt)
            if self.status == "playing" and not self.enemies and not self.spawn_queue:
                bonus = 250 + (self.wave * 35 if self.mode == "endless" else 0)
                self.score += bonus
                self.waves_cleared += 1
                self.projectiles.clear()
                if self.mode != "endless" and self.wave == WAVE_COUNT:
                    self.finish("victory")
                else:
                    if self.mode == "endless":
                        heal = 15 if self.wave % 5 == 0 else 6
                        self.player["health"] = min(self.player["max_health"], self.player["health"] + heal)
                    self.phase, self.phase_clock = "intermission", 2.8
                    self.say(f"Sector secured. +{bonus} points" + (f" / +{heal} hull" if self.mode == "endless" else ""), 2.8)
        for pickup in self.pickups[:]:
            x, y = pickup["pos"]
            pickup["age"] += dt
            energy = pickup["kind"] == "energy"
            gap = distance(pickup["pos"], self.player["pos"])
            if energy and (gap < 145 or self.phase == "intermission") and gap > 0:
                px, py = self.player["pos"]
                travel = min(gap, (540 if self.phase == "intermission" else 350) * dt)
                pickup["pos"] = (x + (px - x) / gap * travel, y + (py - y) / gap * travel)
            else:
                pickup["pos"] = (x, y + (70 if energy else 90) * dt)
            if self.status == "playing" and distance(pickup["pos"], self.player["pos"]) < 40:
                collected = self.collect_energy(pickup.get("value", 1)) if energy else self.collect_powerup(pickup["kind"])
                if collected:
                    self.pickups.remove(pickup)
            elif pickup["pos"][1] > HEIGHT + 25 or pickup["age"] > 14:
                self.pickups.remove(pickup)
        for particle in self.particles:
            x, y = particle["pos"]
            vx, vy = particle["velocity"]
            particle["pos"] = (x + vx * dt, y + vy * dt)
            particle["life"] -= dt
        self.particles = [p for p in self.particles if p["life"] > 0]
        self.radar_clock -= dt
        if self.radar_clock <= 0:
            self.update_threat_ranking()
            self.radar_clock = .2
