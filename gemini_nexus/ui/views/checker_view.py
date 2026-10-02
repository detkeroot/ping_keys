"""Checker view for executing batch key validation with telemetry and logs."""

import time
from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gemini_nexus.core.config import DEFAULT_MODELS
from gemini_nexus.core.db import Database
from gemini_nexus.ui.widgets.log_viewer import LogViewer
from gemini_nexus.ui.workers.check_worker import CheckWorker


class CheckerView(QWidget):
    """View managing validation parameters, worker lifecycle, telemetry, and live logs."""

    def __init__(self, db: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.worker: CheckWorker | None = None
        self._start_time: float = 0.0

        self._init_ui()
        self.load_settings()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Configuration Panel
        config_frame = QFrame()
        config_frame.setObjectName("configFrame")
        config_frame.setStyleSheet("""
            QFrame#configFrame {
                background-color: #1a1a1e;
                border: 1px solid #2d2d34;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        config_layout = QVBoxLayout(config_frame)
        config_layout.setContentsMargins(10, 8, 10, 8)
        config_layout.setSpacing(8)

        # Row 1: Model & Delays
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        lbl_model = QLabel("Модель:")
        lbl_model.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(220)

        lbl_delay_min = QLabel("Задержка мин (сек):")
        self.delay_min_spin = QDoubleSpinBox()
        self.delay_min_spin.setRange(0.5, 60.0)
        self.delay_min_spin.setSingleStep(0.5)
        self.delay_min_spin.setValue(7.0)

        lbl_delay_max = QLabel("макс:")
        self.delay_max_spin = QDoubleSpinBox()
        self.delay_max_spin.setRange(0.5, 60.0)
        self.delay_max_spin.setSingleStep(0.5)
        self.delay_max_spin.setValue(10.0)

        row1.addWidget(lbl_model)
        row1.addWidget(self.model_combo)
        row1.addWidget(lbl_delay_min)
        row1.addWidget(self.delay_min_spin)
        row1.addWidget(lbl_delay_max)
        row1.addWidget(self.delay_max_spin)
        row1.addStretch()

        # Row 2: Proxy settings
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        self.proxy_enable_check = QCheckBox("Использовать прокси")
        self.proxy_enable_check.toggled.connect(self._on_proxy_toggled)

        self.proxy_url_input = QLineEdit()
        self.proxy_url_input.setPlaceholderText("socks5://127.0.0.1:1080 или http://user:pass@host:port")
        self.proxy_url_input.setEnabled(False)

        row2.addWidget(self.proxy_enable_check)
        row2.addWidget(self.proxy_url_input, stretch=1)

        config_layout.addLayout(row1)
        config_layout.addLayout(row2)
        layout.addWidget(config_frame)

        # 2. Action Controls
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)

        self.btn_start_full = QPushButton("🚀 Запуск полной проверки")
        self.btn_start_full.setStyleSheet("""
            QPushButton {
                background-color: #2980b9;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #3498db; }
            QPushButton:disabled { background-color: #333338; color: #777; }
        """)
        self.btn_start_full.clicked.connect(self.start_full_check)
        self.start_full_btn = self.btn_start_full

        self.btn_start_selected = QPushButton("🎯 Выборочная проверка")
        self.btn_start_selected.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #9b59b6; }
            QPushButton:disabled { background-color: #333338; color: #777; }
        """)
        self.btn_start_selected.clicked.connect(self.start_selected_check)
        self.start_selected_btn = self.btn_start_selected

        self.btn_pause = QPushButton("⏸️ Пауза")
        self.btn_pause.setEnabled(False)
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background-color: #d35400;
                color: white;
                font-weight: bold;
                padding: 8px 14px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #e67e22; }
            QPushButton:disabled { background-color: #333338; color: #777; }
        """)
        self.btn_pause.clicked.connect(self.toggle_pause)
        self.pause_btn = self.btn_pause

        self.btn_stop = QPushButton("⏹️ Стоп")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #c0392b;
                color: white;
                font-weight: bold;
                padding: 8px 14px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #e74c3c; }
            QPushButton:disabled { background-color: #333338; color: #777; }
        """)
        self.btn_stop.clicked.connect(self.stop_check)
        self.stop_btn = self.btn_stop

        actions_row.addWidget(self.btn_start_full)
        actions_row.addWidget(self.btn_start_selected)
        actions_row.addWidget(self.btn_pause)
        actions_row.addWidget(self.btn_stop)
        actions_row.addStretch()

        layout.addLayout(actions_row)

        # 3. Live Telemetry Cards
        telemetry_layout = QHBoxLayout()
        telemetry_layout.setSpacing(8)

        card_total_frame, self.card_total = self._create_card("Всего ключей", "0", "#3498db")
        card_chk_frame, self.card_checked = self._create_card("Проверено", "0", "#ecf0f1")
        card_ok_frame, self.card_ok = self._create_card("Работает (OK)", "0", "#2ecc71")
        card_lim_frame, self.card_limits = self._create_card("Лимиты (429)", "0", "#f39c12")
        card_err_frame, self.card_errors = self._create_card("Ошибки / Бан", "0", "#e74c3c")
        card_spd_frame, self.card_speed = self._create_card("Скорость", "0.0 к/с", "#1abc9c")

        telemetry_layout.addWidget(card_total_frame)
        telemetry_layout.addWidget(card_chk_frame)
        telemetry_layout.addWidget(card_ok_frame)
        telemetry_layout.addWidget(card_lim_frame)
        telemetry_layout.addWidget(card_err_frame)
        telemetry_layout.addWidget(card_spd_frame)

        layout.addLayout(telemetry_layout)

        # 4. Animated / Styled Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(18)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1a1a1e;
                border: 1px solid #2d2d34;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                font-weight: bold;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #27ae60, stop:1 #2ecc71);
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 5. Embedded Log Viewer
        lbl_log = QLabel("Журнал проверки:")
        lbl_log.setStyleSheet("font-weight: bold; color: #a0a0a0; font-size: 12px;")
        layout.addWidget(lbl_log)

        self.log_viewer = LogViewer()
        layout.addWidget(self.log_viewer, stretch=1)

    def _create_card(self, title: str, default_val: str, color: str) -> tuple[QFrame, QLabel]:
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #1a1a1e;
                border: 1px solid #2a2a2e;
                border-radius: 8px;
                padding: 6px;
            }
        """)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(6, 6, 6, 6)
        card_layout.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet("color: #888888; font-size: 11px;")

        lbl_val = QLabel(default_val)
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_val.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold;")

        card_layout.addWidget(lbl_title)
        card_layout.addWidget(lbl_val)
        return card, lbl_val

    def _on_proxy_toggled(self, checked: bool) -> None:
        self.proxy_url_input.setEnabled(checked)

    def load_settings(self) -> None:
        """Populate model selector and settings from database."""
        # Load models
        models = self.db.get_models()
        if not models:
            for m in DEFAULT_MODELS:
                self.db.add_model(m)
            models = self.db.get_models()

        self.model_combo.clear()
        self.model_combo.addItems(models)

        # Active model
        current_model = self.db.get_setting("current_model", DEFAULT_MODELS[0] if DEFAULT_MODELS else "")
        if current_model in models:
            self.model_combo.setCurrentText(current_model)

        # Delays
        try:
            d_min = float(self.db.get_setting("delay_min", "7.0"))
            self.delay_min_spin.setValue(d_min)
        except ValueError:
            self.delay_min_spin.setValue(7.0)

        try:
            d_max = float(self.db.get_setting("delay_max", "10.0"))
            self.delay_max_spin.setValue(d_max)
        except ValueError:
            self.delay_max_spin.setValue(10.0)

        # Proxy
        use_proxy = self.db.get_setting("proxy_use", "0") == "1"
        self.proxy_enable_check.setChecked(use_proxy)
        self.proxy_url_input.setEnabled(use_proxy)
        self.proxy_url_input.setText(self.db.get_setting("proxy_url", "socks5://127.0.0.1:1080"))

    def save_settings(self) -> None:
        """Persist current configuration to database."""
        self.db.set_setting("current_model", self.model_combo.currentText())
        self.db.set_setting("delay_min", str(self.delay_min_spin.value()))
        self.db.set_setting("delay_max", str(self.delay_max_spin.value()))
        self.db.set_setting("proxy_use", "1" if self.proxy_enable_check.isChecked() else "0")
        self.db.set_setting("proxy_url", self.proxy_url_input.text().strip())

    def start_full_check(self) -> None:
        """Initiate verification for all non-ignored keys."""
        all_keys = self.db.get_keys()
        active_keys = [k for k in all_keys if not k.get("is_ignored")]
        self._start_worker_with_keys(active_keys)

    def start_selected_check(self) -> None:
        """Initiate verification for UNCHECKED or non-OK keys."""
        all_keys = self.db.get_keys()
        unchecked = [k for k in all_keys if k.get("status") == "UNCHECKED" and not k.get("is_ignored")]
        if not unchecked:
            unchecked = [k for k in all_keys if k.get("status") != "OK" and not k.get("is_ignored")]
        self._start_worker_with_keys(unchecked)

    def _start_worker_with_keys(self, keys: list[dict[str, Any]]) -> None:
        if not keys:
            self.log_viewer.append_log("Нет доступных ключей для проверки.", "WARN")
            return

        self.save_settings()

        self.btn_start_full.setEnabled(False)
        self.btn_start_selected.setEnabled(False)
        self.btn_pause.setEnabled(True)
        self.btn_pause.setText("⏸️ Пауза")
        self.btn_stop.setEnabled(True)

        self._start_time = time.time()
        self.progress_bar.setRange(0, len(keys))
        self.progress_bar.setValue(0)

        self.card_total.setText(str(len(keys)))
        self.card_checked.setText("0")
        self.card_ok.setText("0")
        self.card_limits.setText("0")
        self.card_errors.setText("0")
        self.card_speed.setText("0.0 к/с")

        model = self.model_combo.currentText()
        proxy_url = self.proxy_url_input.text().strip() if self.proxy_enable_check.isChecked() else None
        d_min = self.delay_min_spin.value()
        d_max = self.delay_max_spin.value()

        self.worker = CheckWorker(
            keys_to_check=keys,
            model=model,
            proxy_url=proxy_url,
            delay_min=d_min,
            delay_max=d_max,
            parent=self,
        )

        self.worker.progress_updated.connect(self._on_progress_updated)
        self.worker.stats_updated.connect(self._on_stats_updated)
        self.worker.log_emitted.connect(self._on_log_emitted)
        self.worker.key_finished.connect(self._on_key_finished)
        self.worker.all_finished.connect(self._on_all_finished)

        self.worker.start()

    def toggle_pause(self) -> None:
        """Toggle pause and resume state on the running worker."""
        if not self.worker:
            return

        if self.worker._is_paused:
            self.worker.resume()
            self.btn_pause.setText("⏸️ Пауза")
        else:
            self.worker.pause()
            self.btn_pause.setText("▶️ Возобновить")

    def stop_check(self) -> None:
        """Signal running worker to immediately cancel."""
        if self.worker:
            self.worker.stop()
            self.btn_pause.setText("⏸️ Пауза")
            self.btn_pause.setEnabled(False)

    def _on_progress_updated(self, current: int, total: int) -> None:
        self.progress_bar.setMaximum(max(1, total))
        self.progress_bar.setValue(current)

    def _on_stats_updated(self, stats: dict[str, Any]) -> None:
        checked = stats.get("checked", 0)
        self.card_total.setText(str(stats.get("total", 0)))
        self.card_checked.setText(str(checked))
        self.card_ok.setText(str(stats.get("ok", 0)))
        self.card_limits.setText(str(stats.get("limits", 0)))

        errs = stats.get("errors", 0) + stats.get("dead", 0)
        self.card_errors.setText(str(errs))

        elapsed = time.time() - self._start_time
        if elapsed > 0.5 and checked > 0:
            speed = checked / elapsed
            self.card_speed.setText(f"{speed:.1f} к/с")

    def _on_log_emitted(self, text: str, tag: str) -> None:
        self.log_viewer.append_log(text, tag)

    def _on_key_finished(self, key_id: int, status: str, detail: str) -> None:
        self.db.update_key_status(key_id, status, detail)

    def _on_all_finished(self) -> None:
        self.btn_start_full.setEnabled(True)
        self.btn_start_selected.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setText("⏸️ Пауза")
        self.btn_stop.setEnabled(False)
