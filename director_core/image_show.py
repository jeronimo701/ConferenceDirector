from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel, QWidget


class FullScreenImage(QWidget):
    def __init__(self, screen):
        super().__init__()
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setStyleSheet("background-color: black;")
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setGeometry(self.rect())
        self.pixmap = QPixmap()
        self.showFullScreen()
        self.setGeometry(screen.geometry())

    def show_image(self, path):
        self.pixmap = QPixmap(path)
        self.repaint_image()

    def resizeEvent(self, event):
        self.label.setGeometry(self.rect())
        self.repaint_image()

    def repaint_image(self):
        if self.pixmap.isNull() or self.label.width() <= 0:
            return
        self.label.setPixmap(
            self.pixmap.scaled(self.label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
