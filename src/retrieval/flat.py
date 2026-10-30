"""Flat top-k retrieval over the statute provisions: BM25, and dense embeddings for comparison.

Each provision (section, exception or explanation) is indexed as "<label>: <text>". Illustrations
are left out: their facts ("A lets B a house...") look like lease clauses and crowd out the
provisions (dev, 30 Oct: dense section recall@5 0.40 with them, 0.55 without).

On dev, BM25 beats the dense index (section recall@5 0.78 against 0.55), so "flat" is BM25.
The dense encoder is any function from a list of strings to unit-length vectors, so tests can
pass a toy one; the default is BGE-small on CPU, without BGE's query prefix (worse on dev).
"""

import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Callable

from src.common.jsonl import read_jsonl
from src.common.schemas import StatuteNode

STATUTE = Path(__file__).resolve().parents[2] / "data/statute/nodes.jsonl"
DENSE_MODEL = "BAAI/bge-small-en-v1.5"

Encoder = Callable[[list[str]], list[list[float]]]


def node_text(n: StatuteNode) -> str:
    return f"{n.label}: {n.text}"


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class FlatIndex:
    """Scores every node against the query and returns the top k."""

    def __init__(self, nodes: list[StatuteNode], score: Callable[[str], list[float]]):
        self.nodes = nodes
        self.score = score

    def search(self, query: str, k: int = 5) -> list[StatuteNode]:
        scores = self.score(query)
        order = sorted(range(len(self.nodes)), key=lambda i: -scores[i])
        return [self.nodes[i] for i in order[:k]]

    @classmethod
    def dense(cls, nodes: list[StatuteNode], encode: Encoder, query_prefix: str = "") -> "FlatIndex":
        vecs = encode([node_text(n) for n in nodes])

        def score(query: str) -> list[float]:
            [q] = encode([query_prefix + query])
            return [sum(a * b for a, b in zip(q, v)) for v in vecs]

        return cls(nodes, score)

    @classmethod
    def bm25(cls, nodes: list[StatuteNode], k1: float = 1.5, b: float = 0.75) -> "FlatIndex":
        docs = [Counter(tokens(node_text(n))) for n in nodes]
        lengths = [sum(d.values()) for d in docs]
        avg = sum(lengths) / len(lengths)
        df = Counter(t for d in docs for t in d)
        idf = {t: math.log(1 + (len(docs) - f + 0.5) / (f + 0.5)) for t, f in df.items()}

        def score(query: str) -> list[float]:
            q = set(tokens(query))
            return [
                sum(idf[t] * d[t] * (k1 + 1) / (d[t] + k1 * (1 - b + b * n / avg)) for t in q if t in d)
                for d, n in zip(docs, lengths)
            ]

        return cls(nodes, score)


def st_encoder(model: str = DENSE_MODEL) -> Encoder:
    from sentence_transformers import SentenceTransformer

    net = SentenceTransformer(model, device="cpu")
    return lambda texts: net.encode(texts, normalize_embeddings=True, batch_size=32).tolist()


@lru_cache(maxsize=None)
def provisions(path: str = str(STATUTE)) -> tuple[StatuteNode, ...]:
    return tuple(n for n in read_jsonl(path, StatuteNode) if n.type in ("section", "exception", "explanation"))


@lru_cache(maxsize=None)
def dense_index(model: str = DENSE_MODEL) -> FlatIndex:
    return FlatIndex.dense(list(provisions()), st_encoder(model))


@lru_cache(maxsize=None)
def bm25_index() -> FlatIndex:
    return FlatIndex.bm25(list(provisions()))
