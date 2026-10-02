"""Dark themed real-time log viewer widget for Gemini Nexus DB."""

import html
from datetime import datetime

from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QPlainTextEdit, QWidget


class LogViewer(QPlainTextEdit):
    """High-contrast dark-mode terminal log viewer with colored status tags."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(1000)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #121214;
                color: #e0e0e0;
                font-family: 'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', 'Consolas', monospace;
                font-size: 12px;
                border: 1px solid #2a2a2e;
                border-radius: 6px;
                padding: 4px;
            }
        """)

    def append_log(self, text: str, tag: str = "INFO") -> None:
        """Format and append a timestamped log entry with tag-based color styling.

        Args:
            text: Log message body.
            tag: Status or category tag (e.g., 'OK', 'WARN', 'LIMIT', 'ERROR', 'DEAD', 'SYS', 'INFO').
        """
        time_str = datetime.now().astimezone().strftime("%H:%M:%S")
        upper_tag = tag.upper()

        if upper_tag in ("OK", "SUCCESS"):
            color = "#2ecc71"
        elif upper_tag in ("WARN", "LIMIT", "WARNING"):
            color = "#f39c12"
        elif upper_tag in ("ERROR", "DEAD", "FAIL", "CRITICAL"):
            color = "#e74c3c"
        elif upper_tag in ("SYS", "SYSTEM"):
            color = "#3498db"
        else:
            color = "#a0a0a0"

        escaped_text = html.escape(text)
        html_line = (
            f"<span style='color: #666;'>[{time_str}]</span> "
            f"<span style='color: {color}; font-weight: bold;'>[{upper_tag}]</span> "
            f"{escaped_text}"
        )
        self.appendHtml(html_line)
        self.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self) -> None:
        """Clear all log entries from the viewer."""
        self.clear()
