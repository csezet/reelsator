import os
import urllib.request
import re

ICONS = [
    "camera",
    "sliders-horizontal",
    "folder",
    "folder-open",
    "zap",
    "layers",
    "trash-2",
    "crop",
    "sparkles",
    "image",
    "star",
    "smartphone",
    "cpu",
    "flame",
    "film",
    "shield-check",
]

BASE_URL = "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{name}.svg"
DEST_DIR = os.path.abspath("assets/icons")

def main():
    os.makedirs(DEST_DIR, exist_ok=True)
    print(f"Downloading {len(ICONS)} icons to {DEST_DIR}...")
    
    for name in ICONS:
        url = BASE_URL.format(name=name)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urllib.request.urlopen(req) as resp:
                svg_content = resp.read().decode("utf-8")
                
            dest_path = os.path.join(DEST_DIR, f"{name}.svg")
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
            print(f"Downloaded: {name}.svg")
        except Exception as e:
            print(f"Failed to download {name}: {e}")

if __name__ == "__main__":
    main()
