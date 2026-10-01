"""Unit tests for SQLite database repository."""
import pytest
from gemini_nexus.core.db import Database


@pytest.fixture
def test_db(tmp_path):
    """Fixture providing an initialized temporary database."""
    db_path = tmp_path / "test_gemini.db"
    db = Database(str(db_path))
    db.init_db()
    return db


def test_database_init_and_owners(test_db):
    """Verifies init_db, add_owner, and get_owners with key_count."""
    owner_id = test_db.add_owner("@test_donator", "VIP donator")
    assert owner_id > 0

    owners = test_db.get_owners()
    assert len(owners) == 1
    assert owners[0]["id"] == owner_id
    assert owners[0]["nickname"] == "@test_donator"
    assert owners[0]["notes"] == "VIP donator"
    assert owners[0]["key_count"] == 0

    # Add a key for this owner and verify key_count increases
    test_db.add_keys(owner_id, ["AIzaSyTest123"])
    owners = test_db.get_owners()
    assert owners[0]["key_count"] == 1


def test_database_add_keys_and_deduplication(test_db):
    """Verifies adding duplicate keys returns correct (added, duplicates) count."""
    owner_id = test_db.add_owner("@donor1", "")
    keys = ["KEY_A_111", "KEY_B_222", "KEY_A_111", "   ", "KEY_C_333"]
    added, dupes = test_db.add_keys(owner_id, keys)
    assert added == 3
    assert dupes == 1

    all_keys = test_db.get_keys()
    assert len(all_keys) == 3

    # Add duplicates again
    added2, dupes2 = test_db.add_keys(owner_id, ["KEY_B_222", "KEY_NEW"])
    assert added2 == 1
    assert dupes2 == 1
    assert len(test_db.get_keys()) == 4


def test_database_status_update_and_ignore(test_db):
    """Verifies update_key_status and toggle_key_ignored."""
    owner_id = test_db.add_owner("@donor2", "")
    test_db.add_keys(owner_id, ["KEY_XYZ"])
    key = test_db.get_keys()[0]

    test_db.update_key_status(key["id"], "RESOURCE_EXHAUSTED", "Quota limit 429")
    updated = test_db.get_keys()[0]
    assert updated["status"] == "RESOURCE_EXHAUSTED"
    assert updated["detail"] == "Quota limit 429"

    new_state = test_db.toggle_key_ignored(key["id"])
    assert new_state is True
    assert test_db.get_keys()[0]["is_ignored"] == 1

    new_state2 = test_db.toggle_key_ignored(key["id"])
    assert new_state2 is False
    assert test_db.get_keys()[0]["is_ignored"] == 0


def test_database_cascading_delete(test_db):
    """Verifies deleting an owner cascades to delete all linked keys."""
    owner1_id = test_db.add_owner("@donor_to_delete", "temporary")
    owner2_id = test_db.add_owner("@donor_keep", "permanent")

    test_db.add_keys(owner1_id, ["KEY_DEL_1", "KEY_DEL_2"])
    test_db.add_keys(owner2_id, ["KEY_KEEP_1"])

    assert len(test_db.get_keys()) == 3

    test_db.delete_owner(owner1_id)

    owners = test_db.get_owners()
    assert len(owners) == 1
    assert owners[0]["id"] == owner2_id

    remaining_keys = test_db.get_keys()
    assert len(remaining_keys) == 1
    assert remaining_keys[0]["key_string"] == "KEY_KEEP_1"


def test_database_models_and_settings(test_db):
    """Verifies get_models, add_model, get_setting, and set_setting."""
    models = test_db.get_models()
    assert isinstance(models, list)
    assert "gemini-3.8-flash" in models

    # Add new model
    added = test_db.add_model("custom-future-model")
    assert added is True
    assert "custom-future-model" in test_db.get_models()

    # Add duplicate model
    added_dupe = test_db.add_model("custom-future-model")
    assert added_dupe is False

    # Empty model name
    assert test_db.add_model("   ") is False

    # Settings
    assert test_db.get_setting("non_existent", "default_val") == "default_val"
    test_db.set_setting("delay_min", "15")
    assert test_db.get_setting("delay_min") == "15"
    test_db.set_setting("delay_min", "20")
    assert test_db.get_setting("delay_min") == "20"


def test_database_search_filter(test_db):
    """Verifies get_keys with status filtering and search query."""
    owner_id = test_db.add_owner("@search_tester", "note_owner")
    test_db.add_keys(owner_id, ["KEY_ACTIVE", "KEY_BROKEN", "KEY_IGNORED", "KEY_SPECIAL"])

    keys = {k["key_string"]: k["id"] for k in test_db.get_keys()}

    test_db.update_key_status(keys["KEY_ACTIVE"], "OK", "Working fine")
    test_db.update_key_status(keys["KEY_BROKEN"], "FAILED_PRECONDITION", "Region blocked")
    test_db.toggle_key_ignored(keys["KEY_IGNORED"])

    # Filter: Все
    assert len(test_db.get_keys("Все")) == 4

    # Filter: Активные (OK)
    ok_keys = test_db.get_keys("Активные (OK)")
    assert len(ok_keys) == 1
    assert ok_keys[0]["key_string"] == "KEY_ACTIVE"

    # Filter: Ошибки (not OK and not UNCHECKED)
    err_keys = test_db.get_keys("Ошибки")
    assert len(err_keys) == 1
    assert err_keys[0]["key_string"] == "KEY_BROKEN"

    # Filter: Игнорируемые
    ign_keys = test_db.get_keys("Игнорируемые")
    assert len(ign_keys) == 1
    assert ign_keys[0]["key_string"] == "KEY_IGNORED"

    # Specific status filter
    failed_keys = test_db.get_keys("FAILED_PRECONDITION")
    assert len(failed_keys) == 1
    assert failed_keys[0]["key_string"] == "KEY_BROKEN"

    # Search query matching key_string
    search_res = test_db.get_keys(search_query="SPECIAL")
    assert len(search_res) == 1
    assert search_res[0]["key_string"] == "KEY_SPECIAL"

    # Search query matching owner nickname
    search_owner = test_db.get_keys(search_query="search_tester")
    assert len(search_owner) == 4


def test_database_reset_and_delete_broken(test_db):
    """Verifies reset_statuses and delete_broken_keys."""
    owner_id = test_db.add_owner("@reset_donor")
    test_db.add_keys(owner_id, ["K1", "K2", "K3", "K4"])
    keys = {k["key_string"]: k["id"] for k in test_db.get_keys()}

    test_db.update_key_status(keys["K1"], "OK", "all good")
    test_db.update_key_status(keys["K2"], "UNAUTHORIZED", "bad key")
    test_db.update_key_status(keys["K3"], "RESOURCE_EXHAUSTED", "wait")
    test_db.update_key_status(keys["K4"], "PERMISSION_DENIED", "banned")

    # Reset single key status or all
    test_db.reset_statuses(owner_id)
    for k in test_db.get_keys():
        assert k["status"] == "UNCHECKED"
        assert k["detail"] == ""

    # Re-apply broken statuses
    test_db.update_key_status(keys["K1"], "OK", "")
    test_db.update_key_status(keys["K2"], "UNAUTHORIZED", "")
    test_db.update_key_status(keys["K4"], "PERMISSION_DENIED", "")

    deleted = test_db.delete_broken_keys()
    assert deleted == 2  # K2 and K4 deleted
    remaining = [k["key_string"] for k in test_db.get_keys()]
    assert "K1" in remaining
    assert "K3" in remaining
    assert "K2" not in remaining
    assert "K4" not in remaining

    # Test delete_key
    test_db.delete_key(keys["K1"])
    assert len(test_db.get_keys()) == 1
