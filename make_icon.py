from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


assets = Path(__file__).resolve().parent / "assets"
renderer = QSvgRenderer(str(assets / "tidy-logo.svg"))
canvas = QImage(512, 512, QImage.Format.Format_ARGB32)
canvas.fill(QColor(Qt.GlobalColor.transparent))
painter = QPainter(canvas)
renderer.render(painter)
painter.end()
png = assets / "tidy-logo.png"
canvas.save(str(png))
Image.open(png).save(assets / "tidy.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
