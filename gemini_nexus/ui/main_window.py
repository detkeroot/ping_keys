"""Main window shell and navigation orchestrator for Gemini Nexus DB."""

import sqlite3

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QCloseEvent, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gemini_nexus.core.config import APP_NAME, APP_VERSION, AUTHOR
from gemini_nexus.core.db import Database
from gemini_nexus.ui.views import (
    CheckerView,
    InfoView,
    ManagerView,
    SplitterView,
)


class MainWindow(QMainWindow):
    """Primary application window featuring sidebar navigation and stacked views."""

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db

        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — Enterprise Key Orchestrator by {AUTHOR}")
        self.resize(1200, 800)
        self.setMinimumSize(960, 620)

        self._init_ui()
        self.update_status_summary()

    def _init_ui(self) -> None:
        """Construct sidebar and stacked views layout."""
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Sidebar
        self.sidebar = self._build_sidebar()
        root_layout.addWidget(self.sidebar)

        # 2. Main Stacked Widget
        self.stacked_widget = QStackedWidget(self)
        self.manager_view = ManagerView(self.db)
        self.checker_view = CheckerView(self.db)
        self.splitter_view = SplitterView(self.db)
        self.info_view = InfoView()

        self.stacked_widget.addWidget(self.manager_view)  # Index 0
        self.stacked_widget.addWidget(self.checker_view)  # Index 1
        self.stacked_widget.addWidget(self.splitter_view)  # Index 2
        self.stacked_widget.addWidget(self.info_view)  # Index 3

        root_layout.addWidget(self.stacked_widget, stretch=1)

        # Set default active view: ManagerView
        self._set_active_view(0)

    def _build_sidebar(self) -> QFrame:
        """Create and style the left navigation sidebar."""
        sidebar = QFrame(self)
        sidebar.setObjectName("sidebarFrame")
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("""
            #sidebarFrame {
                background-color: #1a1d24;
                border-right: 1px solid #282c37;
            }
        """)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 18, 12, 18)
        layout.setSpacing(10)

        # Header: Logo & Titles
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(4, 4, 4, 12)
        header_layout.setSpacing(10)

        logo_label = QLabel("⚡")
        logo_label.setStyleSheet("font-size: 26px; color: #00b4d8;")
        header_layout.addWidget(logo_label)

        title_col = QVBoxLayout()
        title_col.setContentsMargins(0, 0, 0, 0)
        title_col.setSpacing(1)

        app_title = QLabel("NEXUS CORE")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        app_title.setFont(title_font)
        app_title.setStyleSheet("color: #ffffff; letter-spacing: 1px;")

        app_subtitle = QLabel(f"v{APP_VERSION} Enterprise")
        app_subtitle.setStyleSheet("color: #7b889b; font-size: 10px; font-weight: 500;")

        title_col.addWidget(app_title)
        title_col.addWidget(app_subtitle)
        header_layout.addLayout(title_col)
        header_layout.addStretch()

        layout.addWidget(header_widget)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color: #282c37; background-color: #282c37; max-height: 1px; margin-bottom: 6px;")
        layout.addWidget(divider)

        # Navigation Buttons
        self.btn_nav_manager = self._create_nav_button("🗄️  База данных", 0)
        self.btn_nav_checker = self._create_nav_button("📡  Чекер ключей", 1)
        self.btn_nav_splitter = self._create_nav_button("🔀  Сплиттер потоков", 2)
        self.btn_nav_info = self._create_nav_button("ℹ️  Справка / FAQ", 3)

        self.nav_buttons = [
            self.btn_nav_manager,
            self.btn_nav_checker,
            self.btn_nav_splitter,
            self.btn_nav_info,
        ]

        for btn in self.nav_buttons:
            layout.addWidget(btn)

        layout.addStretch()

        # Bottom Sidebar: Status and key counter
        bottom_box = QFrame()
        bottom_box.setObjectName("sidebarBottomBox")
        bottom_box.setStyleSheet("""
            #sidebarBottomBox {
                background-color: #21252f;
                border: 1px solid #2e3442;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        bottom_layout = QVBoxLayout(bottom_box)
        bottom_layout.setContentsMargins(8, 8, 8, 8)
        bottom_layout.setSpacing(4)

        lbl_caption = QLabel("СОСТОЯНИЕ ХРАНИЛИЩА")
        lbl_caption.setStyleSheet("color: #64748b; font-size: 9px; font-weight: bold; letter-spacing: 0.5px;")
        bottom_layout.addWidget(lbl_caption)

        self.lbl_key_counter = QLabel("Ключей в базе: 0")
        self.lbl_key_counter.setStyleSheet("color: #e2e8f0; font-size: 11px; font-weight: 600;")
        bottom_layout.addWidget(self.lbl_key_counter)

        layout.addWidget(bottom_box)

        return sidebar

    def _create_nav_button(self, title: str, index: int) -> QPushButton:
        """Create styled navigation button for sidebar."""
        btn = QPushButton(title)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(42)
        btn.clicked.connect(lambda: self._set_active_view(index))
        return btn

    def _set_active_view(self, index: int) -> None:
        """Switch stacked widget index and update button active highlight styling."""
        self.stacked_widget.setCurrentIndex(index)

        # Style navigation buttons
        for idx, btn in enumerate(self.nav_buttons):
            if idx == index:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2563eb;
                        color: #ffffff;
                        font-weight: bold;
                        text-align: left;
                        padding-left: 16px;
                        border-radius: 6px;
                        border: none;
                        font-size: 12px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #94a3b8;
                        font-weight: normal;
                        text-align: left;
                        padding-left: 16px;
                        border-radius: 6px;
                        border: none;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background-color: #21252f;
                        color: #f1f5f9;
                    }
                """)

        # Refresh counter when navigating
        self.update_status_summary()

    def update_status_summary(self) -> None:
        """Refresh summary metrics displayed in the sidebar."""
        try:
            keys = self.db.get_keys()
            total = len(keys)
            ok_count = sum(1 for k in keys if k.get("status") == "OK")
            self.lbl_key_counter.setText(f"Ключей: {total} | Активных: {ok_count}")
        except (sqlite3.Error, OSError, AttributeError):
            self.lbl_key_counter.setText("Ключей: 0 | Активных: 0")

    def closeEvent(self, event: QCloseEvent | None) -> None:
        """Safely intercept window closure and terminate active background worker."""
        if (
            hasattr(self, "checker_view")
            and getattr(self.checker_view, "worker", None) is not None
            and self.checker_view.worker.isRunning()
        ):
            self.checker_view.stop_check()
            self.checker_view.worker.wait(1000)

        if event is not None:
            event.accept()
        super().closeEvent(event)
