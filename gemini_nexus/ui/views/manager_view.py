"""Manager view for API key repository, donors, filtering, and table interactions."""

from typing import Any, ClassVar

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QPoint, Qt
from PyQt6.QtGui import QAction, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from gemini_nexus.core.config import STATUS_COLORS, STATUS_RU
from gemini_nexus.core.db import Database


class KeyTableModel(QAbstractTableModel):
    """Virtualized table data model for API keys in Gemini Nexus DB."""

    HEADERS: ClassVar[tuple[str, ...]] = (
        "ID",
        "Донатер",
        "Ключ API",
        "Статус",
        "Детали ошибки",
        "Заметка",
        "Игнор",
    )

    def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
        super().__init__()
        self._data: list[dict[str, Any]] = data or []

    def rowCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._data)

    def columnCount(self, parent: QModelIndex | None = None) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self.HEADERS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None

        row_item = self._data[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(row_item.get("id", ""))
            elif col == 1:
                return str(row_item.get("owner_nickname") or "Общий / Анонимный")
            elif col == 2:
                key_str = str(row_item.get("key_string", ""))
                # Display full key or slightly formatted
                return key_str
            elif col == 3:
                status = str(row_item.get("status") or "UNCHECKED")
                return STATUS_RU.get(status, status)
            elif col == 4:
                return str(row_item.get("detail", ""))
            elif col == 5:
                return str(row_item.get("notes", ""))
            elif col == 6:
                return "Да" if row_item.get("is_ignored") else "Нет"

        elif role == Qt.ItemDataRole.ForegroundRole:
            if col == 3:
                status = str(row_item.get("status") or "UNCHECKED")
                color_hex = STATUS_COLORS.get(status, "#7f8c8d")
                return QColor(color_hex)
            if row_item.get("is_ignored"):
                return QColor("#666666")

        elif role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 3, 6):
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        return None

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
            and 0 <= section < len(self.HEADERS)
        ):
            return self.HEADERS[section]
        return None

    def set_data(self, data: list[dict[str, Any]]) -> None:
        """Replace model contents and trigger virtual view refresh."""
        self.beginResetModel()
        self._data = list(data)
        self.endResetModel()

    def get_row_data(self, row: int) -> dict[str, Any]:
        """Return raw dictionary representation of a specific row."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return {}


class ManagerView(QWidget):
    """Primary management view for adding, searching, and managing API keys."""

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db

        self._init_ui()
        self.refresh_donators()
        self.refresh_table()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Top Addition Bar
        add_frame = QFrame()
        add_frame.setObjectName("addFrame")
        add_frame.setStyleSheet("""
            QFrame#addFrame {
                background-color: #1a1a1e;
                border: 1px solid #2d2d34;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        add_layout = QVBoxLayout(add_frame)
        add_layout.setContentsMargins(8, 8, 8, 8)
        add_layout.setSpacing(6)

        donor_row = QHBoxLayout()
        donor_label = QLabel("Донатер:")
        donor_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")

        self.donator_combo = QComboBox()
        self.donator_combo.setMinimumWidth(200)

        self.btn_new_donor = QPushButton("➕ Новый донатер")
        self.btn_new_donor.clicked.connect(self._on_add_new_donor)
        self.add_donor_btn = self.btn_new_donor

        donor_row.addWidget(donor_label)
        donor_row.addWidget(self.donator_combo)
        donor_row.addWidget(self.btn_new_donor)
        donor_row.addStretch()

        self.keys_input = QPlainTextEdit()
        self.keys_input.setPlaceholderText("Вставьте Gemini API ключи (по одному на строку)...")
        self.keys_input.setMaximumHeight(85)
        self.keys_input.setStyleSheet("""
            QPlainTextEdit {
                background-color: #121214;
                color: #e0e0e0;
                font-family: monospace;
                border: 1px solid #2a2a2e;
                border-radius: 6px;
                padding: 6px;
            }
        """)

        save_row = QHBoxLayout()
        save_row.addStretch()
        self.btn_save_keys = QPushButton("💾 Сохранить ключи")
        self.btn_save_keys.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        self.btn_save_keys.clicked.connect(self.save_keys)
        self.save_keys_btn = self.btn_save_keys
        save_row.addWidget(self.btn_save_keys)

        add_layout.addLayout(donor_row)
        add_layout.addWidget(self.keys_input)
        add_layout.addLayout(save_row)

        layout.addWidget(add_frame)

        # 2. Search & Filter Bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Поиск по ключу, донатеру, заметке...")
        self.search_input.textChanged.connect(self.refresh_table)

        self.status_filter_combo = QComboBox()
        self.status_filter_combo.addItems(
            [
                "Все",
                "Активные (OK)",
                "Лимиты (429)",
                "Ошибки",
                "Игнорируемые",
            ]
        )
        self.status_filter_combo.currentTextChanged.connect(self.refresh_table)

        self.refresh_btn = QPushButton("🔄 Обновить")
        self.refresh_btn.clicked.connect(self.refresh_table)

        self.delete_dead_btn = QPushButton("🗑️ Удалить мёртвые")
        self.delete_dead_btn.setStyleSheet("color: #e74c3c;")
        self.delete_dead_btn.clicked.connect(self.delete_dead_keys)

        self.reset_all_btn = QPushButton("⚡ Сбросить статусы")
        self.reset_all_btn.setStyleSheet("color: #f39c12;")
        self.reset_all_btn.clicked.connect(self.reset_all_statuses)

        filter_layout.addWidget(self.search_input, stretch=2)
        filter_layout.addWidget(QLabel("Статус:"))
        filter_layout.addWidget(self.status_filter_combo)
        filter_layout.addWidget(self.refresh_btn)
        filter_layout.addWidget(self.delete_dead_btn)
        filter_layout.addWidget(self.reset_all_btn)

        layout.addLayout(filter_layout)

        # 3. Table View
        self.table_view = QTableView()
        self.table_model = KeyTableModel()
        self.table_view.setModel(self.table_model)

        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table_view.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.verticalHeader().setVisible(False)
        self.table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self._show_context_menu)
        self.table_view.doubleClicked.connect(self._on_cell_double_clicked)

        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table_view, stretch=1)

    def refresh_donators(self) -> None:
        """Fetch owners from database and repopulate dropdown."""
        current_id = self.donator_combo.currentData()
        self.donator_combo.clear()

        owners = self.db.get_owners()
        target_idx = 0
        for idx, o in enumerate(owners):
            nick = o.get("nickname", "Unnamed")
            count = o.get("key_count", 0)
            self.donator_combo.addItem(f"{nick} ({count} шт.)", userData=o.get("id"))
            if current_id is not None and o.get("id") == current_id:
                target_idx = idx

        if self.donator_combo.count() > 0:
            self.donator_combo.setCurrentIndex(target_idx)

    def refresh_table(self) -> None:
        """Query database with current search and status filters and update table model."""
        status_filter = self.status_filter_combo.currentText()
        search_query = self.search_input.text().strip()
        keys = self.db.get_keys(status_filter=status_filter, search_query=search_query)
        self.table_model.set_data(keys)

    def save_keys(self) -> None:
        """Parse raw keys from input box and insert into database."""
        raw_text = self.keys_input.toPlainText()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        if not lines:
            return

        owner_id = self.donator_combo.currentData()
        if owner_id is None:
            # Create a default owner if none exists
            owner_id = self.db.add_owner("Общий / Анонимный")

        self.db.add_keys(owner_id, lines)
        self.keys_input.clear()
        self.refresh_donators()
        self.refresh_table()

    def _on_add_new_donor(self) -> None:
        """Prompt user for a new donor nickname and save to database."""
        nick, ok = QInputDialog.getText(
            self,
            "Новый донатер",
            "Введите никнейм или идентификатор донатера:",
        )
        if ok and nick.strip():
            new_id = self.db.add_owner(nick.strip())
            self.refresh_donators()
            # Select the newly added donor
            for idx in range(self.donator_combo.count()):
                if self.donator_combo.itemData(idx) == new_id:
                    self.donator_combo.setCurrentIndex(idx)
                    break

    def _on_cell_double_clicked(self, index: QModelIndex) -> None:
        """Double clicking a cell copies the key string to clipboard."""
        row_data = self.table_model.get_row_data(index.row())
        key_str = row_data.get("key_string", "")
        if key_str:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(key_str)

    def _show_context_menu(self, pos: QPoint) -> None:
        """Display context menu with key-level operational actions."""
        index = self.table_view.indexAt(pos)
        if not index.isValid():
            return

        row_data = self.table_model.get_row_data(index.row())
        key_id = row_data.get("id")
        key_str = row_data.get("key_string", "")
        is_ignored = bool(row_data.get("is_ignored"))
        current_notes = row_data.get("notes", "")

        menu = QMenu(self)

        copy_action = QAction("📋 Копировать ключ", self)
        copy_action.triggered.connect(lambda: self._copy_to_clipboard(key_str))
        menu.addAction(copy_action)

        ignore_text = "👁️ Включить" if is_ignored else "👁️ Игнорировать"
        toggle_ignore_action = QAction(ignore_text, self)
        toggle_ignore_action.triggered.connect(lambda: self.toggle_key_ignore(key_id))
        menu.addAction(toggle_ignore_action)

        reset_action = QAction("⚡ Сбросить статус", self)
        reset_action.triggered.connect(lambda: self.reset_key_status(key_id))
        menu.addAction(reset_action)

        edit_note_action = QAction("✏️ Изменить заметку", self)
        edit_note_action.triggered.connect(lambda: self.edit_key_note(key_id, current_notes))
        menu.addAction(edit_note_action)

        menu.addSeparator()

        delete_action = QAction("❌ Удалить ключ", self)
        delete_action.triggered.connect(lambda: self.delete_single_key(key_id))
        menu.addAction(delete_action)

        menu.exec(self.table_view.viewport().mapToGlobal(pos))

    def _copy_to_clipboard(self, text: str) -> None:
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def toggle_key_ignore(self, key_id: int) -> None:
        """Toggle ignore state for the given key ID."""
        self.db.toggle_key_ignored(key_id)
        self.refresh_table()

    def reset_key_status(self, key_id: int) -> None:
        """Reset validation status of key to UNCHECKED."""
        self.db.update_key_status(key_id, "UNCHECKED", "")
        self.refresh_table()

    def edit_key_note(self, key_id: int, current_note: str) -> None:
        """Display dialog to modify key notes."""
        note, ok = QInputDialog.getText(
            self,
            "Заметка для ключа",
            "Редактировать заметку:",
            text=current_note,
        )
        if ok:
            self.db.update_key_notes(key_id, note)
            self.refresh_table()

    def delete_single_key(self, key_id: int) -> None:
        """Delete an individual key by ID."""
        self.db.delete_key(key_id)
        self.refresh_donators()
        self.refresh_table()

    def delete_dead_keys(self) -> None:
        """Delete all keys with unrecoverable / fatal error statuses."""
        self.db.delete_broken_keys()
        self.refresh_donators()
        self.refresh_table()

    def reset_all_statuses(self) -> None:
        """Reset validation statuses of all keys to UNCHECKED."""
        self.db.reset_statuses()
        self.refresh_table()
