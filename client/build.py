"""
DoomScroll Detox - client/build.py

Convenience wrapper around `pyinstaller build.spec`.

Usage:
    pip install pyinstaller
    python build.py

Produces a standalone distributable in dist/DoomScrollDetox/
(a DoomScrollDetox.app bundle too, on macOS).
"""

import subprocess
import sys


def main() -> None:
    print("[build] Running PyInstaller (this can take a few minutes -- "
          "EasyOCR/PyTorch are large)...")
    try:
        subprocess.run(
            [sys.executable, "-m", "PyInstaller", "build.spec", "--noconfirm"],
            check=True,
        )
    except FileNotFoundError:
        print(
            "[build] PyInstaller isn't installed. Install it with:\n"
            "    pip install pyinstaller"
        )
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        print(f"[build] PyInstaller build failed (exit code {exc.returncode}).")
        sys.exit(exc.returncode)

    print("\n[build] Done. Find your distributable in dist/DoomScrollDetox/")
    if sys.platform == "darwin":
        print("[build] macOS app bundle: dist/DoomScrollDetox.app")


if __name__ == "__main__":
    main()
