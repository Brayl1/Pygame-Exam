"""Nested wave definitions and bounded, meaningful recursion."""

WORLD_WIDTH = 920
WORLD_HEIGHT = 600
WAVE_COUNT = 5


def expand_formation(node: dict, origin: tuple = (0.0, 0.0),
                     start_time: float = 0.0, depth: int = 0) -> list[dict]:
    """Return spawn instructions for every leaf of a formation tree.

    Base cases: an enemy leaf yields one spawn; an empty group yields none.
    Every recursive call descends into a child (a smaller subtree). The
    depth guard also rejects accidentally over-nested input.
    """
    if depth > 12:
        raise ValueError("Formation nesting exceeds 12 levels")
    offset = node.get("offset", (0, 0))
    position = (origin[0] + offset[0], origin[1] + offset[1])
    spawn_time = start_time + node.get("delay", 0)
    if "kind" in node:
        if node["kind"] not in {"scout", "heavy", "boss"}:
            raise ValueError("Unknown enemy kind")
        return [{"kind": node["kind"], "pos": position, "time": spawn_time}]
    result = []
    for child in node.get("children", []):
        result.extend(expand_formation(child, position, spawn_time, depth + 1))
    return result


def squad(kind: str, center_x: float, count: int,
          delay: float, spacing: float = 110) -> dict:
    return {
        "offset": (center_x, -65), "delay": delay,
        "children": [{"kind": kind,
                      "offset": ((i - (count - 1) / 2) * spacing, -abs(i - (count - 1) / 2) * 28),
                      "delay": i * .18} for i in range(count)],
    }


def wave_tree(number: int) -> dict:
    """Five finite missions, ending with a boss and two escort squads."""
    if number == 1:
        groups = [squad("scout", 460, 3, 0), squad("scout", 460, 3, 3.8)]
    elif number == 2:
        groups = [squad("scout", 460, 4, 0), squad("heavy", 460, 2, 3),
                  squad("scout", 460, 4, 5.8)]
    elif number == 3:
        groups = [squad("heavy", 460, 3, 0, 210),
                  {"delay": 2.2, "children": [squad("scout", 250, 3, 0),
                                               squad("scout", 670, 3, 1.8)]}]
    elif number == 4:
        groups = [squad("scout", 460, 5, 0, 130),
                  squad("heavy", 460, 4, 2.5, 185),
                  squad("scout", 460, 5, 5.8, 130)]
    elif number == 5:
        groups = [{"kind": "boss", "offset": (460, -140)},
                  {"delay": 6, "children": [squad("scout", 230, 2, 0),
                                             squad("scout", 690, 2, 1.5)]}]
    else:
        raise ValueError("Wave number must be between 1 and 5")
    return {"children": groups}


def endless_wave_tree(number: int) -> dict:
    """Generate one bounded wave at a time; recursion depth never grows.

    The wave index can grow indefinitely. Each generated tree contains at most
    30 normal ships or a boss with escorts, in staggered nested formations.
    """
    if type(number) is not int or number < 1:
        raise ValueError("Endless wave number must be a positive integer")
    if number % 5 == 0:
        escort_count = min(5, 2 + number // 10)
        return {"children": [
            {"kind": "boss", "offset": (460, -140)},
            {"delay": 2.0, "children": [
                squad("scout", 240, escort_count, 0, 75),
                squad("scout", 680, escort_count, 2.5, 75)]},
            {"delay": 6, "children": [squad("heavy", 460, min(4, 1 + number // 10), 0, 145)]},
        ]}
    groups = []
    group_count = min(5, 2 + number // 4)
    count = min(6, 3 + number // 6)
    for index in range(group_count):
        kind = "heavy" if number >= 3 and (number + index) % 3 == 0 else "scout"
        center = (360, 560, 460)[(number + index) % 3]
        groups.append({"delay": index * 2.5,
                       "children": [squad(kind, center, count, 0, 95)]})
    return {"children": groups}
