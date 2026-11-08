import hashlib
import math
import re

EMBEDDING_DIMENSION = 192


def embed_text(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    for token in re.findall(r"[\w.-]{2,}", text.lower()):
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def cosine_similarity(left: list[float] | None, right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    return sum(a * b for a, b in zip(left, right))
