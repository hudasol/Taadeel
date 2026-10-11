"""Alignment of articles across two versions of a law.

Monotonic dynamic programming over a pairwise score that blends normalized
text similarity, relative position, and (weakly) number equality. Pairs that
score below ``t_low`` are never forced: they go to the unaligned buckets.
Limitation (documented): monotonic order means an article that *moves* far
within the law is reported as repealed + inserted, not as a move.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from .model import Expression, Provision

T_MATCH = 0.60
T_LOW = 0.35
AMBIGUITY_MARGIN = 0.05   # rival candidate within this score => low confidence


@dataclass(frozen=True)
class Alignment:
    a_eid: str
    b_eid: str
    score: float
    confidence: str   # "high" | "low"


@dataclass
class AlignmentResult:
    pairs: list[Alignment]
    unaligned_a: list[str]    # present in A only (candidates: repealed)
    unaligned_b: list[str]    # present in B only (candidates: inserted)


def _trigrams(s: str) -> set[str]:
    s = f" {s} "
    return {s[i : i + 3] for i in range(max(len(s) - 2, 1))}


def text_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    ta, tb = _trigrams(a), _trigrams(b)
    jac = len(ta & tb) / len(ta | tb)
    ratio = SequenceMatcher(None, a.split(), b.split(), autojunk=False).ratio()
    return 0.5 * jac + 0.5 * ratio


def pair_score(a: Provision, b: Provision, i: int, n: int, j: int, m: int) -> float:
    text = text_similarity(a.text_norm, b.text_norm)
    pa = i / (n - 1) if n > 1 else 0.0
    pb = j / (m - 1) if m > 1 else 0.0
    prior = 1.0 - abs(pa - pb)
    numeq = 1.0 if a.key == b.key else 0.0
    return 0.85 * text + 0.10 * prior + 0.05 * numeq


def align(a: Expression, b: Expression, t_match: float = T_MATCH, t_low: float = T_LOW) -> AlignmentResult:
    A, B = a.articles(), b.articles()
    n, m = len(A), len(B)
    NEG = float("-inf")
    w = [[NEG] * m for _ in range(n)]
    S = [[0.0] * m for _ in range(n)]
    for i in range(n):
        for j in range(m):
            s = pair_score(A[i], B[j], i, n, j, m)
            S[i][j] = s
            if s >= t_low:
                w[i][j] = s
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best = max(dp[i - 1][j], dp[i][j - 1])
            if w[i - 1][j - 1] != NEG:
                best = max(best, dp[i - 1][j - 1] + w[i - 1][j - 1])
            dp[i][j] = best
    pairs: list[Alignment] = []
    i, j = n, m
    while i > 0 and j > 0:
        if w[i - 1][j - 1] != NEG and abs(dp[i][j] - (dp[i - 1][j - 1] + w[i - 1][j - 1])) < 1e-12:
            s = w[i - 1][j - 1]
            rival_a = max((S[i - 1][k] for k in range(m) if k != j - 1), default=0.0)
            rival_b = max((S[k][j - 1] for k in range(n) if k != i - 1), default=0.0)
            ambiguous = s - max(rival_a, rival_b) < AMBIGUITY_MARGIN
            pairs.append(Alignment(A[i - 1].eid, B[j - 1].eid, round(s, 4),
                                   "high" if s >= t_match and not ambiguous else "low"))
            i, j = i - 1, j - 1
        elif abs(dp[i][j] - dp[i - 1][j]) < 1e-12:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    ma = {p.a_eid for p in pairs}
    mb = {p.b_eid for p in pairs}
    return AlignmentResult(
        pairs=pairs,
        unaligned_a=[p.eid for p in A if p.eid not in ma],
        unaligned_b=[p.eid for p in B if p.eid not in mb],
    )
