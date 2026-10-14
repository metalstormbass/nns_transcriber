import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def run_app():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
