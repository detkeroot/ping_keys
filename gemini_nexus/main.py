"""Main application entrypoint for Gemini Nexus DB."""

import sys
from collections.abc import Sequence

import qdarktheme
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication

from gemini_nexus.core.db import Database
from gemini_nexus.ui.main_window import MainWindow


def main(argv: Sequence[str] | None = None) -> int:
    """Initialize application runtime, high DPI scaling, dark theme, and launch MainWindow."""
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication.instance()
    if app is None:
        args = list(sys.argv if argv is None else argv)
        app = QApplication(args)

    qdarktheme.setup_theme(theme="dark", corner_shape="rounded")

    db = Database()
    db.init_db()

    window = MainWindow(db)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
