"""PyInstaller build script to package Reelsator into a standalone Windows 11 executable."""

import os
import sys
import subprocess
import cv2

def build():
    print("Building Reelsator standalone executable for Windows 11...")

    cascade_dir = cv2.data.haarcascades
    face_xml = os.path.join(cascade_dir, "haarcascade_frontalface_default.xml")
    profile_xml = os.path.join(cascade_dir, "haarcascade_profileface.xml")

    # PyInstaller arguments
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--name=Reelsator",
        "--noconsole",
        "--onedir",
        "--clean",
        "--noconfirm",
        f"--add-data={face_xml};cv2/data",
        f"--add-data={profile_xml};cv2/data",
        "--hidden-import=cv2",
        "--hidden-import=PIL",
        "--hidden-import=piexif",
        "--hidden-import=numpy",
        "--hidden-import=PySide6",
        "app.py"
    ]

    print("Running command:", " ".join(cmd))
    res = subprocess.run(cmd)
    if res.returncode == 0:
        print("\nBuild completed successfully!")
        print("Executable located at: dist/Reelsator/Reelsator.exe")
    else:
        print(f"\nBuild failed with exit code {res.returncode}")

if __name__ == "__main__":
    build()
