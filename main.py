"""Run with: python main.py (Python 3.10+ and Pillow)."""

import sys


def main():
    try:
        import tkinter as tk
        from galaxy.app import GalaxyApp
    except ImportError as exc:
        print(f"Missing dependency: {exc}")
        print("Install Pillow: python -m pip install -r requirements.txt")
        print("Check Tkinter: python -m tkinter")
        return 1
    try:
        root = tk.Tk()
        GalaxyApp(root)
        root.mainloop()
    except tk.TclError as exc:
        print(f"Unable to open the Tkinter window: {exc}")
        print("Run this game on a desktop with a graphical display.")
        return 1
    except (FileNotFoundError, OSError) as exc:
        print(f"Unable to load the game assets: {exc}")
        print("Extract the complete ZIP before running main.py. Keep the assets folder beside it.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
