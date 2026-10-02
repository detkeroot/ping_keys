"""Unit and integration tests for Gemini Nexus PyQt6 Views."""

import pytest
from PyQt6.QtWidgets import QApplication

from gemini_nexus.core.config import DEFAULT_MODELS
from gemini_nexus.core.db import Database
from gemini_nexus.ui.views import (
    CheckerView,
    InfoView,
    ManagerView,
    SplitterView,
)


@pytest.fixture(scope="session")
def qapp():
    """Ensure a headless offscreen QApplication exists for widget testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["-platform", "offscreen"])
    return app


@pytest.fixture
def test_db(tmp_path):
    """Fixture providing an initialized temporary database."""
    db_path = tmp_path / "test_views.db"
    db = Database(str(db_path))
    db.init_db()
    return db


def test_views_instantiation(qapp, test_db):
    """Verify all four primary views instantiate without errors."""
    manager = ManagerView(test_db)
    assert manager is not None
    assert manager.db is test_db

    checker = CheckerView(test_db)
    assert checker is not None
    assert checker.db is test_db

    splitter = SplitterView(test_db)
    assert splitter is not None
    assert splitter.db is test_db

    info = InfoView()
    assert info is not None


def test_manager_view_refresh_and_search(qapp, test_db):
    """Verify ManagerView table loading, searching, and filtering."""
    donor_id = test_db.add_owner("AlphaDonor", "VIP notes")
    test_db.add_keys(donor_id, ["AIzaSyKeyAAA111", "AIzaSyKeyBBB222", "AIzaSyKeyCCC333"])

    # Update statuses
    keys = test_db.get_keys()
    test_db.update_key_status(keys[0]["id"], "OK", "Active key")
    test_db.update_key_status(keys[1]["id"], "RESOURCE_EXHAUSTED", "Quota 429")
    test_db.update_key_status(keys[2]["id"], "PERMISSION_DENIED", "Blocked 403")

    manager = ManagerView(test_db)
    manager.refresh_table()

    # Model should have 3 rows
    assert manager.table_model.rowCount() == 3

    # Test search filter
    manager.search_input.setText("BBB222")
    manager.refresh_table()
    assert manager.table_model.rowCount() == 1
    row_data = manager.table_model.get_row_data(0)
    assert "BBB222" in row_data["key_string"]

    # Clear search and test status combo filter
    manager.search_input.clear()
    manager.status_filter_combo.setCurrentText("Активные (OK)")
    manager.refresh_table()
    assert manager.table_model.rowCount() == 1
    assert manager.table_model.get_row_data(0)["status"] == "OK"

    # Reset filter
    manager.status_filter_combo.setCurrentText("Все")
    manager.refresh_table()
    assert manager.table_model.rowCount() == 3


def test_manager_view_add_donor_and_keys(qapp, test_db):
    """Verify donor creation and batch key addition in ManagerView."""
    manager = ManagerView(test_db)

    # Initial donors
    assert manager.donator_combo.count() == 0

    # Programmatically add donor via db and refresh combo
    test_db.add_owner("BetaDonor")
    manager.refresh_donators()
    assert manager.donator_combo.count() == 1
    assert "BetaDonor" in manager.donator_combo.currentText()

    # Add keys via multiline text edit
    manager.keys_input.setPlainText("AIzaSyNewKey001\nAIzaSyNewKey002\n\nAIzaSyNewKey003  ")
    manager.save_keys()

    # Table should now display the 3 added keys
    assert manager.table_model.rowCount() == 3
    assert manager.keys_input.toPlainText() == ""


def test_manager_view_key_actions(qapp, test_db):
    """Verify toggle ignore, reset status, delete key, and delete dead keys in ManagerView."""
    donor_id = test_db.add_owner("GammaDonor")
    test_db.add_keys(donor_id, ["AIzaSyKeyLive", "AIzaSyKeyDead", "AIzaSyKeyReset"])

    keys = test_db.get_keys()
    test_db.update_key_status(keys[1]["id"], "PERMISSION_DENIED", "Dead key")
    test_db.update_key_status(keys[2]["id"], "RESOURCE_EXHAUSTED", "Limited")

    manager = ManagerView(test_db)
    manager.refresh_table()

    # Toggle ignore on first key
    first_key_id = manager.table_model.get_row_data(0)["id"]
    manager.toggle_key_ignore(first_key_id)
    assert test_db.get_keys()[0]["is_ignored"] == 1

    # Reset single key status
    last_key_id = keys[2]["id"]
    manager.reset_key_status(last_key_id)
    updated_key = next(k for k in test_db.get_keys() if k["id"] == last_key_id)
    assert updated_key["status"] == "UNCHECKED"

    # Delete broken/dead keys
    manager.delete_dead_keys()
    remaining = [k["key_string"] for k in test_db.get_keys()]
    assert "AIzaSyKeyDead" not in remaining

    # Reset all statuses
    manager.reset_all_statuses()
    for k in test_db.get_keys():
        assert k["status"] == "UNCHECKED"


def test_checker_view_model_and_settings(qapp, test_db):
    """Verify CheckerView model selector is populated with DEFAULT_MODELS and settings loaded."""
    checker = CheckerView(test_db)

    # Models should be loaded into selector
    combo_models = [checker.model_combo.itemText(i) for i in range(checker.model_combo.count())]
    for model in DEFAULT_MODELS:
        assert model in combo_models

    # Default settings populated
    assert checker.delay_min_spin.value() >= 1.0
    assert checker.delay_max_spin.value() >= checker.delay_min_spin.value()
    assert checker.proxy_url_input.text() != ""


def test_checker_view_telemetry_and_signals(qapp, test_db):
    """Verify CheckerView telemetry card updates and worker signal slots."""
    checker = CheckerView(test_db)

    # Test progress update slot
    checker._on_progress_updated(5, 10)
    assert checker.progress_bar.value() == 5
    assert checker.progress_bar.maximum() == 10

    # Test stats update slot
    stats = {
        "total": 20,
        "checked": 10,
        "ok": 7,
        "limits": 2,
        "dead": 1,
        "errors": 1,
    }
    checker._on_stats_updated(stats)
    assert "20" in checker.card_total.text()
    assert "10" in checker.card_checked.text()
    assert "7" in checker.card_ok.text()
    assert "2" in checker.card_limits.text()
    assert "2" in checker.card_errors.text()

    # Test log emitted slot
    checker._on_log_emitted("Test log message", "OK")
    assert "Test log message" in checker.log_viewer.toPlainText()


def test_splitter_view_distribution_and_export(qapp, test_db, tmp_path):
    """Verify SplitterView splits keys into streams and exports them."""
    donor_id = test_db.add_owner("SplitterDonor")
    key_list = [f"AIzaSyActiveKey_{i:03d}" for i in range(12)]
    test_db.add_keys(donor_id, key_list)

    # Mark all as OK
    for k in test_db.get_keys():
        test_db.update_key_status(k["id"], "OK")

    splitter = SplitterView(test_db)
    splitter.stream_count_spin.setValue(3)
    splitter.distribute_keys()

    # Should have 3 streams in combo
    assert splitter.stream_combo.count() == 3
    assert "Поток 1" in splitter.stream_combo.itemText(0)

    # Preview area should show 4 keys for stream 1
    stream_1_text = splitter.preview_edit.toPlainText().strip().splitlines()
    assert len(stream_1_text) == 4

    # Switch to stream 2
    splitter.stream_combo.setCurrentIndex(1)
    stream_2_text = splitter.preview_edit.toPlainText().strip().splitlines()
    assert len(stream_2_text) == 4

    # Export to directory
    export_dir = tmp_path / "exports"
    export_dir.mkdir()
    files_created = splitter.export_streams_to_directory(str(export_dir))
    assert len(files_created) == 3
    for f in files_created:
        assert f.exists()
        assert len(f.read_text(encoding="utf-8").strip().splitlines()) == 4


def test_info_view(qapp):
    """Verify InfoView contains helpful documentation, status codes, and guidelines."""
    info = InfoView()
    assert info is not None
    content = info.get_info_text()
    assert "Gemini Nexus" in content
    assert "RESOURCE_EXHAUSTED" in content
    assert "gemini-3.8-flash" in content
    assert "NeuroStarNet" in content


def test_manager_view_clipboard_and_cell_double_click(qapp, test_db):
    """Verify double-clicking a table cell copies key string to clipboard."""
    donor_id = test_db.add_owner("ClipDonor")
    test_db.add_keys(donor_id, ["AIzaSyClipboardTestKey123"])

    manager = ManagerView(test_db)
    manager.refresh_table()

    index = manager.table_model.index(0, 2)
    manager._on_cell_double_clicked(index)

    clipboard = QApplication.clipboard()
    assert clipboard.text() == "AIzaSyClipboardTestKey123"


def test_manager_view_edit_note_and_delete_single(qapp, test_db):
    """Verify editing a note and deleting a single key in ManagerView."""
    donor_id = test_db.add_owner("NoteDonor")
    test_db.add_keys(donor_id, ["AIzaSyKeyForNote"])
    key_id = test_db.get_keys()[0]["id"]

    manager = ManagerView(test_db)
    test_db.update_key_notes(key_id, "Updated custom note")
    manager.refresh_table()
    assert manager.table_model.get_row_data(0)["notes"] == "Updated custom note"

    # Delete single key
    manager.delete_single_key(key_id)
    assert len(test_db.get_keys()) == 0
    assert manager.table_model.rowCount() == 0


def test_checker_view_worker_controls_and_empty_check(qapp, test_db, monkeypatch):
    """Verify checker start with empty keys, and lifecycle controls with keys."""
    checker = CheckerView(test_db)

    # Start check with empty keys
    checker.start_full_check()
    assert "Нет доступных ключей" in checker.log_viewer.toPlainText()

    # Add a key
    donor_id = test_db.add_owner("WorkerDonor")
    test_db.add_keys(donor_id, ["AIzaSyWorkerKeyTest"])

    # Mock check_api_key to avoid real network call
    monkeypatch.setattr(
        "gemini_nexus.ui.workers.check_worker.check_api_key",
        lambda key, model, proxy: ("OK", "Mocked OK"),
    )

    checker.start_full_check()
    assert checker.worker is not None
    assert checker.btn_pause.isEnabled()
    assert checker.btn_stop.isEnabled()

    # Toggle pause
    checker.toggle_pause()
    assert checker.worker._is_paused is True
    assert checker.btn_pause.text() == "▶️ Возобновить"

    # Toggle resume
    checker.toggle_pause()
    assert checker.worker._is_paused is False
    assert checker.btn_pause.text() == "⏸️ Пауза"

    # Stop
    checker.stop_check()
    assert checker.worker._is_running is False
    checker.worker.wait(2000)


def test_splitter_view_copy_clipboard_and_empty_keys(qapp, test_db):
    """Verify copying stream to clipboard and handling zero active keys."""
    splitter = SplitterView(test_db)
    # Zero keys initially - creates empty streams
    splitter.distribute_keys()
    assert splitter.stream_combo.count() == 3
    assert "0 шт." in splitter.stream_combo.itemText(0)
    assert splitter.preview_edit.toPlainText() == ""
    # Add active key
    donor_id = test_db.add_owner("CopyDonor")
    test_db.add_keys(donor_id, ["AIzaSySplitterCopyKey"])
    test_db.update_key_status(test_db.get_keys()[0]["id"], "OK")

    splitter.distribute_keys()
    assert splitter.stream_combo.count() == 3
    splitter.copy_current_stream()

    clipboard = QApplication.clipboard()
    assert "AIzaSySplitterCopyKey" in clipboard.text()
