"""Status badge widget for visual status indication in tables and cards."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QWidget

from gemini_nexus.core.config import STATUS_COLORS, STATUS_RU


class StatusBadge(QLabel):
    """Badge widget displaying localized status text with color-coded styling."""

    def __init__(self, status: str = "UNCHECKED", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(status)

    def set_status(self, status: str | None) -> None:
        """Update badge text and visual appearance based on status code."""
        st = status if status else "UNCHECKED"
        color = STATUS_COLORS.get(st, "#7f8c8d")
        text = STATUS_RU.get(st, st)
        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color}22;
                color: {color};
                border: 1px solid {color}55;
                border-radius: 4px;
                padding: 2px 6px;
                font-weight: bold;
                font-size: 11px;
            }}
        """)
