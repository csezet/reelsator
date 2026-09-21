"""PyInstaller build script to package Reelsator into a standalone Windows 11 executable."""

import os
import sys
import subprocess


def build():
    print("Building Reelsator standalone executable for Windows 11 using Reelsator.spec...")

    # Build directly from the portable Reelsator.spec
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "Reelsator.spec",
    ]

    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\nBuild completed successfully!")
        print("Executable located at: dist/Reelsator/Reelsator.exe")
    else:
        print(f"\nBuild failed with exit code {res.returncode}")
        sys.exit(res.returncode)


if __name__ == "__main__":
    build()
