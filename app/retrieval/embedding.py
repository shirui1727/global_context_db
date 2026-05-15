import math

import numpy as np


def embed_text(text: str, dim: int = 64) -> np.ndarray:
    vec = np.zeros(dim, dtype=np.float32)
    for token in text.lower().split():
        idx = abs(hash(token)) % dim
        vec[idx] += 1.0
    norm = float(np.linalg.norm(vec))
    return vec if norm == 0 else vec / norm

