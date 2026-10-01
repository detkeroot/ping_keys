"""Zero-dependency authenticated stream cipher module.

Provides symmetric encryption and decryption using PBKDF2-HMAC-SHA256,
CTR stream keystream generation, and HMAC-SHA256 authentication.
Pure Python standard library implementation with zero external C-dependencies.
"""

import base64
import hashlib
import hmac
import secrets
from typing import Optional


def encrypt_data(data_str: str, password: str) -> str:
    """Encrypts a string using PBKDF2-HMAC-SHA256, CTR stream keystream and HMAC-SHA256 authentication.

    Format:
        base64(salt [16B] + iv [16B] + tag [32B] + ciphertext [varB])
    """
    salt = secrets.token_bytes(16)
    # Derive 64 bytes: 32 bytes for CTR keystream seed, 32 bytes for HMAC
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000, dklen=64)
    enc_key, hmac_key = derived[:32], derived[32:]

    iv = secrets.token_bytes(16)
    plaintext_bytes = data_str.encode("utf-8")

    # CTR mode generator
    ciphertext = bytearray()
    counter = 0
    for i in range(0, len(plaintext_bytes), 32):
        counter_bin = counter.to_bytes(16, "big")
        keystream_block = hashlib.sha256(enc_key + iv + counter_bin).digest()
        chunk = plaintext_bytes[i : i + 32]
        for b_plain, b_key in zip(chunk, keystream_block):
            ciphertext.append(b_plain ^ b_key)
        counter += 1

    tag = hmac.new(hmac_key, iv + ciphertext, hashlib.sha256).digest()
    final_payload = salt + iv + tag + bytes(ciphertext)
    return base64.b64encode(final_payload).decode("utf-8")


def decrypt_data(payload_str: str, password: str) -> Optional[str]:
    """Decrypts a base64 payload. Returns None if password is wrong or integrity check fails.

    Supports:
        1. Modern format: salt [16B] + iv [16B] + tag [32B] + ciphertext [varB] (CTR 16-byte counter)
        2. Backward-compatible v13.x format: salt [16B] + iv [16B] + ciphertext [varB] + tag [32B]
    """
    try:
        payload = base64.b64decode(payload_str.encode("utf-8"))
        if len(payload) < 64:  # 16 salt + 16 iv + 32 tag
            return None

        # --- 1. Try Modern format (tag at 32:64, iv + ciphertext authenticated) ---
        salt = payload[:16]
        iv = payload[16:32]
        tag = payload[32:64]
        ciphertext = payload[64:]

        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000, dklen=64)
        enc_key, hmac_key = derived[:32], derived[32:]

        expected_tag = hmac.new(hmac_key, iv + ciphertext, hashlib.sha256).digest()
        if hmac.compare_digest(tag, expected_tag):
            plaintext = bytearray()
            counter = 0
            for i in range(0, len(ciphertext), 32):
                counter_bin = counter.to_bytes(16, "big")
                keystream_block = hashlib.sha256(enc_key + iv + counter_bin).digest()
                chunk = ciphertext[i : i + 32]
                for b_cipher, b_key in zip(chunk, keystream_block):
                    plaintext.append(b_cipher ^ b_key)
                counter += 1
            return plaintext.decode("utf-8")

        # --- 2. Fallback: v13.x format (tag at end: payload[:-32] authenticated) ---
        tag_v13 = payload[-32:]
        payload_raw_v13 = payload[:-32]
        if len(payload_raw_v13) >= 32:
            salt_v13 = payload_raw_v13[:16]
            iv_v13 = payload_raw_v13[16:32]
            encrypted_bytes_v13 = payload_raw_v13[32:]

            derived_v13 = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt_v13, 100000, dklen=64
            )
            enc_k_v13, hmac_k_v13 = derived_v13[:32], derived_v13[32:]
            expected_tag_v13 = hmac.new(hmac_k_v13, payload_raw_v13, hashlib.sha256).digest()

            if hmac.compare_digest(tag_v13, expected_tag_v13):
                decrypted_bytes = bytearray()
                for block_idx, i in enumerate(range(0, len(encrypted_bytes_v13), 32)):
                    counter_bin = block_idx.to_bytes(8, "big")
                    keystream = hashlib.sha256(enc_k_v13 + iv_v13 + counter_bin).digest()
                    chunk = encrypted_bytes_v13[i : i + 32]
                    for b, k in zip(chunk, keystream):
                        decrypted_bytes.append(b ^ k)
                return decrypted_bytes.decode("utf-8")

        return None
    except Exception:
        return None
