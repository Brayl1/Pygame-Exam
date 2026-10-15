"""Load original PNGs once; crop transparent margins and cache Tk images."""

from collections import OrderedDict
from pathlib import Path
import math
from PIL import Image, ImageTk, ImageOps, ImageFont, ImageDraw


class AssetManager:
    def __init__(self, directory: Path, master):
        self.master = master
        self.images = {}
        self.cache = OrderedDict()
        files = {
            "player": "ships/player_ship.png", "scout": "ships/enemy_scout.png",
            "heavy": "ships/enemy_heavy.png", "boss": "ships/boss_ship.png",
            "shield": "powerups/powerup_shield.png", "repair": "powerups/powerup_repair.png",
            "rapid_fire": "powerups/powerup_rapid_fire.png",
            "laser": "projectiles/projectile_player.png", "plasma": "projectiles/projectile_enemy.png",
        }
        for name, relative in files.items():
            with Image.open(directory / relative) as source:
                image = source.convert("RGBA")
            bounds = image.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
            self.images[name] = image.crop(bounds) if bounds else image
        with Image.open(directory / "backgrounds/space_background.png") as source:
            self.background = source.convert("RGB")

    def sprite(self, name: str, width: float, scale: float):
        target_width = max(1, round(width * scale))
        key = (name, target_width)
        if key not in self.cache:
            image = self.images[name]
            target_height = max(1, round(image.height * target_width / image.width))
            self.cache[key] = ImageTk.PhotoImage(image.resize((target_width, target_height),
                                                            Image.Resampling.LANCZOS), master=self.master)
            while len(self.cache) > 180:
                self.cache.popitem(last=False)
        self.cache.move_to_end(key)
        return self.cache[key]

    def backdrop(self, width: int, height: int):
        return ImageTk.PhotoImage(ImageOps.fit(self.background, (max(1, width), max(1, height)),
                                              method=Image.Resampling.LANCZOS), master=self.master)


class TextRenderer:
    """Consistent scalable Canvas lettering, including minimal Linux desktops.

    Tkinter remains the GUI framework. Pillow rasterizes the bundled licensed
    fonts, and Tk PhotoImage displays them. Caching avoids redrawing unchanged
    labels every frame. The callsign input is still a native Tk Entry widget.
    """
    def __init__(self, directory: Path, master):
        self.directory = directory
        self.master = master
        self.fonts = {}
        self.cache = OrderedDict()

    def render(self, text: str, size: int, color: str, bold=False, wrap_width=0):
        key = (str(text), size, color, bold, wrap_width)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        font_key = (size, bold)
        if font_key not in self.fonts:
            filename = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
            self.fonts[font_key] = ImageFont.truetype(str(self.directory / filename), size)
        font = self.fonts[font_key]
        lines = []
        for paragraph in str(text).split('\n'):
            if not wrap_width:
                lines.append(paragraph)
                continue
            current = ''
            for word in paragraph.split():
                candidate = current + ' ' + word if current else word
                if current and font.getlength(candidate) > wrap_width:
                    lines.append(current)
                    current = word
                else:
                    current = candidate
            lines.append(current)
        ascent, descent = font.getmetrics()
        line_height = ascent + descent + 2
        top = font.getbbox('Ag')[1]
        image_width = max(1, math.ceil(max((font.getlength(line) for line in lines), default=0)) + 4)
        image_height = max(1, line_height * len(lines) + 4)
        picture = Image.new('RGBA', (image_width, image_height))
        draw = ImageDraw.Draw(picture)
        for index, line in enumerate(lines):
            draw.text((2, 2 + index * line_height - top), line, font=font, fill=color)
        photo = ImageTk.PhotoImage(picture, master=self.master)
        self.cache[key] = photo
        while len(self.cache) > 512:
            self.cache.popitem(last=False)
        return photo
