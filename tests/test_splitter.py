"""Unit tests for Gemini Nexus stream splitter and load balancer."""
import pytest
from gemini_nexus.core.splitter import (
    split_keys_round_robin,
    filter_active_keys,
)


def test_split_empty():
    """Verifies empty keys list with 3 streams returns {1: [], 2: [], 3: []}."""
    res = split_keys_round_robin([], 3)
    assert res == {1: [], 2: [], 3: []}


def test_split_even_distribution():
    """Verifies 6 keys across 3 streams distributes [k1, k4], [k2, k5], [k3, k6]."""
    keys = ["k1", "k2", "k3", "k4", "k5", "k6"]
    res = split_keys_round_robin(keys, 3)
    assert res[1] == ["k1", "k4"]
    assert res[2] == ["k2", "k5"]
    assert res[3] == ["k3", "k6"]


def test_split_single_stream():
    """Verifies 1 stream gets all keys."""
    keys = ["k1", "k2", "k3"]
    res = split_keys_round_robin(keys, 1)
    assert res == {1: ["k1", "k2", "k3"]}


def test_split_clamped_num_streams():
    """Verifies non-positive num_streams is clamped to at least 1."""
    keys = ["k1", "k2"]
    res_zero = split_keys_round_robin(keys, 0)
    assert res_zero == {1: ["k1", "k2"]}

    res_neg = split_keys_round_robin(keys, -5)
    assert res_neg == {1: ["k1", "k2"]}


def test_split_uneven_distribution():
    """Verifies uneven distribution across streams."""
    keys = ["k1", "k2", "k3", "k4", "k5"]
    res = split_keys_round_robin(keys, 3)
    assert res == {
        1: ["k1", "k4"],
        2: ["k2", "k5"],
        3: ["k3"],
    }


def test_filter_active_keys():
    """Verifies filtering list of key dicts returns only those with status == 'OK' and not is_ignored."""
    sample_keys = [
        {"id": 1, "key_string": "KEY_1", "status": "OK", "is_ignored": 0},
        {"id": 2, "key_string": "KEY_2", "status": "RESOURCE_EXHAUSTED", "is_ignored": 0},
        {"id": 3, "key_string": "KEY_3", "status": "OK", "is_ignored": 1},
        {"id": 4, "key_string": "KEY_4", "status": "UNCHECKED", "is_ignored": 0},
        {"id": 5, "key_string": "KEY_5", "status": "OK", "is_ignored": False},
        {"id": 6, "key_string": "KEY_6", "status": "API_KEY_INVALID", "is_ignored": 0},
        {"id": 7, "key_string": "KEY_7", "status": "OK", "is_ignored": True},
    ]

    active = filter_active_keys(sample_keys)
    assert active == ["KEY_1", "KEY_5"]
