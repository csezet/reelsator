import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer

COLORS = {
    "accent": "#818cf8",
    "white": "#ffffff",
    "muted": "#9ca3af",
    "indigo": "#6366f1",
    "emerald": "#34d399",
}

SIZES = [16, 20, 24, 32]

def main():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    src_dir = os.path.abspath("assets/icons")
    png_dir = os.path.join(src_dir, "png")
    os.makedirs(png_dir, exist_ok=True)

    svg_files = [f for f in os.listdir(src_dir) if f.endswith(".svg")]
    print(f"Rendering {len(svg_files)} SVGs to PNG...")

    for fname in svg_files:
        name = os.path.splitext(fname)[0]
        svg_path = os.path.join(src_dir, fname)
        with open(svg_path, "r", encoding="utf-8") as f:
            raw_svg = f.read()

        for cname, ccode in COLORS.items():
            colored_svg = raw_svg.replace("currentColor", ccode)
            renderer = QSvgRenderer(colored_svg.encode("utf-8"))

            for size in SIZES:
                pixmap = QPixmap(size, size)
                pixmap.fill(QColor(0, 0, 0, 0))
                painter = QPainter(pixmap)
                renderer.render(painter)
                painter.end()

                out_name = f"{name}_{cname}_{size}px.png"
                pixmap.save(os.path.join(png_dir, out_name), "PNG")

    print(f"Generated pre-rendered PNG icons in {png_dir}")

if __name__ == "__main__":
    main()
