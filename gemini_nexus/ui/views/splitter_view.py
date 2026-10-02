"""Splitter view for Round-Robin distribution and export of active API keys."""

from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gemini_nexus.core.db import Database
from gemini_nexus.core.splitter import filter_active_keys, split_keys_round_robin


class SplitterView(QWidget):
    """View managing multi-stream distribution, live preview, and export of active keys."""

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self._streams: dict[int, list[str]] = {}

        self._init_ui()
        self._load_saved_stream_count()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Top Controls Bar
        control_frame = QFrame()
        control_frame.setObjectName("controlFrame")
        control_frame.setStyleSheet("""
            QFrame#controlFrame {
                background-color: #1a1a1e;
                border: 1px solid #2d2d34;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        control_layout = QHBoxLayout(control_frame)
        control_layout.setContentsMargins(8, 6, 8, 6)
        control_layout.setSpacing(12)

        lbl_streams = QLabel("Количество потоков:")
        lbl_streams.setStyleSheet("font-weight: bold; color: #e0e0e0;")

        self.stream_count_spin = QSpinBox()
        self.stream_count_spin.setRange(1, 50)
        self.stream_count_spin.setValue(3)
        self.stream_count_spin.setFixedWidth(70)

        self.btn_distribute = QPushButton("🔀 Распределить ключи")
        self.btn_distribute.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #3498db; }
        """)
        self.btn_distribute.clicked.connect(self.distribute_keys)

        self.lbl_stats = QLabel("Активных ключей: 0")
        self.lbl_stats.setStyleSheet("color: #a0a0a0; font-size: 12px;")

        control_layout.addWidget(lbl_streams)
        control_layout.addWidget(self.stream_count_spin)
        control_layout.addWidget(self.btn_distribute)
        control_layout.addWidget(self.lbl_stats)
        control_layout.addStretch()

        layout.addWidget(control_frame)

        # 2. Stream Selector Bar
        selector_row = QHBoxLayout()
        selector_row.setSpacing(10)

        lbl_select = QLabel("Выбор потока для просмотра:")
        lbl_select.setStyleSheet("font-weight: bold; color: #e0e0e0;")

        self.stream_combo = QComboBox()
        self.stream_combo.setMinimumWidth(220)
        self.stream_combo.currentIndexChanged.connect(self._on_stream_changed)

        selector_row.addWidget(lbl_select)
        selector_row.addWidget(self.stream_combo)
        selector_row.addStretch()

        layout.addLayout(selector_row)

        # 3. Preview Area
        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setPlaceholderText("Здесь будут отображаться ключи выбранного потока...")
        self.preview_edit.setStyleSheet("""
            QPlainTextEdit {
                background-color: #121214;
                color: #2ecc71;
                font-family: 'JetBrains Mono', 'Fira Code', 'DejaVu Sans Mono', 'Consolas', monospace;
                font-size: 13px;
                border: 1px solid #2a2a2e;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.preview_edit, stretch=1)

        # 4. Action Buttons Bar
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)

        self.btn_copy_stream = QPushButton("📋 Скопировать поток")
        self.btn_copy_stream.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #2ecc71; }
        """)
        self.btn_copy_stream.clicked.connect(self.copy_current_stream)

        self.btn_export_all = QPushButton("💾 Экспорт всех потоков в файлы")
        self.btn_export_all.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #9b59b6; }
        """)
        self.btn_export_all.clicked.connect(self.export_all_streams)

        bottom_row.addWidget(self.btn_copy_stream)
        bottom_row.addWidget(self.btn_export_all)
        bottom_row.addStretch()

        layout.addLayout(bottom_row)

    def _load_saved_stream_count(self) -> None:
        try:
            val = int(self.db.get_setting("splitter_streams", "3"))
            self.stream_count_spin.setValue(max(1, val))
        except ValueError:
            self.stream_count_spin.setValue(3)

    def distribute_keys(self) -> None:
        """Fetch all OK non-ignored keys, distribute round-robin, and update UI."""
        all_keys = self.db.get_keys()
        active_keys = filter_active_keys(all_keys)
        num_streams = self.stream_count_spin.value()

        # Save setting
        self.db.set_setting("splitter_streams", str(num_streams))

        self.lbl_stats.setText(f"Активных ключей: {len(active_keys)}")
        self._streams = split_keys_round_robin(active_keys, num_streams)

        self.stream_combo.blockSignals(True)
        self.stream_combo.clear()

        for stream_id, keys in self._streams.items():
            self.stream_combo.addItem(f"Поток {stream_id} ({len(keys)} шт.)", userData=stream_id)

        self.stream_combo.blockSignals(False)

        if self.stream_combo.count() > 0:
            self.stream_combo.setCurrentIndex(0)
            self._on_stream_changed(0)
        else:
            self.preview_edit.clear()

    def _on_stream_changed(self, index: int) -> None:
        """Update preview text edit with keys of selected stream."""
        if index < 0 or not self._streams:
            self.preview_edit.clear()
            return

        stream_id = self.stream_combo.itemData(index)
        keys = self._streams.get(stream_id, [])
        self.preview_edit.setPlainText("\n".join(keys))

    def copy_current_stream(self) -> None:
        """Copy active stream preview content to clipboard."""
        text = self.preview_edit.toPlainText().strip()
        if not text:
            return

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)

    def export_streams_to_directory(self, dir_path: str) -> list[Path]:
        """Write each stream's keys into stream_N.txt inside dir_path.

        Args:
            dir_path: Target directory path string.

        Returns:
            List of created Path objects.
        """
        target_dir = Path(dir_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        created_files: list[Path] = []
        for stream_id, keys in self._streams.items():
            file_path = target_dir / f"stream_{stream_id}.txt"
            content = "\n".join(keys) + "\n" if keys else ""
            file_path.write_text(content, encoding="utf-8")
            created_files.append(file_path)

        return created_files

    def export_all_streams(self) -> None:
        """Prompt user for destination folder and export all stream files."""
        if not self._streams:
            self.distribute_keys()

        if not self._streams:
            return

        dest_dir = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сохранения файлов потоков",
        )
        if dest_dir:
            created = self.export_streams_to_directory(dest_dir)
            QMessageBox.information(
                self,
                "Экспорт завершён",
                f"Успешно экспортировано {len(created)} файлов потоков в:\n{dest_dir}",
            )
