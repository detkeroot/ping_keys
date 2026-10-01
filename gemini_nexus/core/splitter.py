"""Round-Robin stream splitter and key filter for Gemini Nexus DB."""

from typing import Any, Dict, List


def split_keys_round_robin(keys: List[str], num_streams: int) -> Dict[int, List[str]]:
    """Distributes API keys evenly across N streams using Round-Robin balancing.

    Args:
        keys: List of API key strings.
        num_streams: Number of streams to split keys across. Clamped to at least 1.

    Returns:
        Dict mapping stream ID (1-indexed, 1..num_streams) to list of key strings.
    """
    effective_streams = max(1, num_streams)
    streams: Dict[int, List[str]] = {i: [] for i in range(1, effective_streams + 1)}

    for index, key in enumerate(keys):
        stream_id = (index % effective_streams) + 1
        streams[stream_id].append(key)

    return streams


def filter_active_keys(keys_data: List[Dict[str, Any]]) -> List[str]:
    """Extracts key_string for keys where status is 'OK' and not is_ignored.

    Args:
        keys_data: List of key dictionaries from the database repository.

    Returns:
        List of key_string values for active, valid keys.
    """
    return [
        k["key_string"]
        for k in keys_data
        if k.get("status") == "OK" and not k.get("is_ignored") and "key_string" in k
    ]
