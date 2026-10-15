"""Run-long energy upgrades and bounded projectile patterns."""

WEAPON_TIERS = (
    {"energy": 0, "name": "PULSE", "lanes": 1, "interval": .220, "speed": 680, "unlock": "Single laser"},
    {"energy": 3, "name": "TWIN", "lanes": 2, "interval": .205, "speed": 720, "unlock": "Twin barrels"},
    {"energy": 7, "name": "TRIDENT", "lanes": 3, "interval": .185, "speed": 760, "unlock": "Three-way spread"},
    {"energy": 12, "name": "QUAD", "lanes": 4, "interval": .165, "speed": 800, "unlock": "Four-way spread"},
    {"energy": 18, "name": "FANFIRE", "lanes": 5, "interval": .145, "speed": 840, "unlock": "Five-barrel salvo"},
    {"energy": 26, "name": "PRISM", "lanes": 5, "interval": .130, "speed": 880, "unlock": "Piercing lance, every 3rd salvo"},
    {"energy": 36, "name": "ORBIT", "lanes": 6, "interval": .115, "speed": 920, "unlock": "Two drone cannons"},
    {"energy": 48, "name": "TEMPEST", "lanes": 7, "interval": .100, "speed": 960, "unlock": "Twin homing bolts every 1.6s"},
)

MAX_PLAYER_PROJECTILES = 220
MAX_ENEMY_PROJECTILES = 300
MAX_PICKUPS = 80


def tier_for_energy(energy: int) -> int:
    """Return the zero-based tier. Extra energy still charges Nova and scores."""
    tier = 0
    for index, spec in enumerate(WEAPON_TIERS):
        if energy < spec["energy"]:
            break
        tier = index
    return tier


def spread_angles(count: int) -> tuple:
    """Symmetric firing directions, in radians relative to straight up."""
    return tuple((index - (count - 1) / 2) * .070 for index in range(count))
