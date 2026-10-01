import base64
import hashlib
import hmac
import secrets
import pytest
from gemini_nexus.core.crypto import encrypt_data, decrypt_data


def test_encrypt_decrypt_roundtrip():
    secret_text = "AQ.TestKey_1234567890_SecretData"
    password = "CorrectHorseBatteryStaple123!"

    encrypted = encrypt_data(secret_text, password)
    assert isinstance(encrypted, str)
    assert encrypted != secret_text

    decrypted = decrypt_data(encrypted, password)
    assert decrypted == secret_text


def test_decrypt_wrong_password():
    secret_text = "SensitiveKeyPayload"
    encrypted = encrypt_data(secret_text, "correct_password")

    decrypted = decrypt_data(encrypted, "wrong_password")
    assert decrypted is None


def test_decrypt_corrupted_payload():
    assert decrypt_data("not_a_valid_base64_payload!", "password") is None

    # Test corrupted valid base64 but invalid length (< 64 bytes)
    short_payload = base64.b64encode(b"short").decode("utf-8")
    assert decrypt_data(short_payload, "password") is None

    # Test corrupted ciphertext / tag alteration
    secret_text = "ValidPayloadToCorrupt"
    valid_encrypted = encrypt_data(secret_text, "test_pass")
    raw = bytearray(base64.b64decode(valid_encrypted.encode("utf-8")))
    # Flip a bit in the tag (bytes 32..64)
    raw[35] ^= 0xFF
    corrupted_tag = base64.b64encode(bytes(raw)).decode("utf-8")
    assert decrypt_data(corrupted_tag, "test_pass") is None

    # Flip a bit in the ciphertext (bytes 64..)
    raw_cipher = bytearray(base64.b64decode(valid_encrypted.encode("utf-8")))
    raw_cipher[-1] ^= 0xFF
    corrupted_cipher = base64.b64encode(bytes(raw_cipher)).decode("utf-8")
    assert decrypt_data(corrupted_cipher, "test_pass") is None


def test_v13_legacy_compatibility():
    """Verify that payloads created with v13.x legacy encrypt_data can be decrypted."""
    secret_text = "Legacy_v13_backup_data_test_12345"
    password = "LegacyPassword123"

    # Simulate legacy v13.x encryption logic
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000, dklen=64)
    enc_key, hmac_key = derived[:32], derived[32:]
    iv = secrets.token_bytes(16)
    data_bytes = secret_text.encode("utf-8")
    encrypted_bytes = bytearray()

    for block_idx, i in enumerate(range(0, len(data_bytes), 32)):
        counter_bin = block_idx.to_bytes(8, "big")
        keystream = hashlib.sha256(enc_key + iv + counter_bin).digest()
        chunk = data_bytes[i : i + 32]
        for b, k in zip(chunk, keystream):
            encrypted_bytes.append(b ^ k)

    payload_raw = salt + iv + bytes(encrypted_bytes)
    tag = hmac.new(hmac_key, payload_raw, hashlib.sha256).digest()
    legacy_payload_b64 = base64.b64encode(payload_raw + tag).decode("utf-8")

    decrypted = decrypt_data(legacy_payload_b64, password)
    assert decrypted == secret_text

    # Wrong password on legacy payload returns None
    assert decrypt_data(legacy_payload_b64, "WrongPassword") is None
