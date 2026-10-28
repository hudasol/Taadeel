"""Alignment v2: background corrected scores, number offset evidence from anchors, and abstention.

A new, separately versioned module. ``align.py`` (v1) is hash locked and unchanged; v1 stays the
default until v2 is shown better on seeds it was never tuned on (docs/PREDICTIONS_V2.md).

Why v1 struggles (held out synthetic, docs/HELDOUT_RESULTS.md): in templated near duplicate laws
every article is about as similar to every other one (median trigram/sequence similarity around
0.66), so v1's monotonic dynamic programme, which adds any pair scoring above 0.35, prefers to pair
a repealed article with a neighbouring inserted one instead of leaving both unaligned. That costs
repealed and inserted recall and creates false "replaced" changes.

v2 changes the pair weight, not the search:

1. **Background correction (evaluated, weight 0 selected).** ``excess = sim - max(bg_a, bg_b)`` where
   ``bg`` is the median similarity of that article to all articles of the other version. The dev
   search (tune_v2.py) gave it weight 0 in every top setting, so the selected v2 does not use it. It
   is kept so that the tuning run can be reproduced.
2. **Anchors and number offsets.** Mutual best pairs with a clear margin are anchors. The longest
   chain of anchors in order fixes, between neighbouring anchors, the expected change in article
   number (later articles shift by one after a plain insertion). A pair whose B number equals the A
   number plus the offset of the anchor on the left or on the right gets number evidence.
3. **Abstention.** The dynamic programme maximises the sum of ``w - tau``; a pair is only taken when
   its weight exceeds ``tau``. Leaving an article unaligned costs nothing, so weak pairs are not forced.

Confidence is "high" only when the pair is an anchor, or its weight clears ``tau`` by ``HIGH_MARGIN``
and no rival in its row or column is within ``AMBIGUITY_MARGIN`` of its similarity.
Limitation kept from v1: order is monotonic, so an article moved far within the law is reported as
repealed plus inserted.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from .align import Alignment, AlignmentResult, text_similarity
from .model import Expression, Provision

VERSION = "align_v2"


@dataclass(frozen=True)
class Params:
    # Defaults = the setting selected on dev seeds 0-29 (results/dev_v2_tuning.json, "best").
    # With these weights a pair is taken if 0.5 * sim > 0.4 (text alone, sim > 0.8) or
    # 0.5 * sim + 0.3 > 0.4 (number evidence, sim > 0.2).
    w_sim: float = 0.5
    w_excess: float = 0.0
    w_num: float = 0.3
    w_prior: float = 0.0
    tau: float = 0.4
    anchor_min: float = 0.80        # anchor needs this similarity ...
    anchor_margin: float = 0.10     # ... and this lead over the second best in its row and column
    high_margin: float = 0.15
    ambiguity_margin: float = 0.05


DEFAULT = Params()


def similarity_matrix(A: list[Provision], B: list[Provision]) -> list[list[float]]:
    return [[text_similarity(a.text_norm, b.text_norm) for b in B] for a in A]


def _anchors(S: list[list[float]], p: Params) -> list[tuple[int, int]]:
    n, m = len(S), len(S[0]) if S else 0
    cand = []
    for i in range(n):
        row = S[i]
        j = max(range(m), key=row.__getitem__)
        col = [S[k][j] for k in range(n)]
        if max(range(n), key=col.__getitem__) != i or row[j] < p.anchor_min:
            continue
        r2 = max((row[k] for k in range(m) if k != j), default=0.0)
        c2 = max((col[k] for k in range(n) if k != i), default=0.0)
        if row[j] - max(r2, c2) >= p.anchor_margin:
            cand.append((i, j))
    # longest chain increasing in both i and j (cand is sorted by i; O(k^2) is fine at law sizes)
    best: list[list[tuple[int, int]]] = []
    for c in cand:
        prev = [b for b in best if b[-1][1] < c[1]]
        best.append((max(prev, key=len) if prev else []) + [c])
    return max(best, key=len) if best else []


def _offsets(A: list[Provision], B: list[Provision], anchors: list[tuple[int, int]]):
    """For each A index: (offset from the anchor at or before it, offset from the anchor at or after it)."""
    n = len(A)
    left: list[int | None] = [None] * n
    right: list[int | None] = [None] * n
    cur = None
    k = 0
    for i in range(n):
        while k < len(anchors) and anchors[k][0] <= i:
            ai, bj = anchors[k]
            if A[ai].number is not None and B[bj].number is not None:
                cur = B[bj].number - A[ai].number
            k += 1
        left[i] = cur
    cur = None
    k = len(anchors) - 1
    for i in range(n - 1, -1, -1):
        while k >= 0 and anchors[k][0] >= i:
            ai, bj = anchors[k]
            if A[ai].number is not None and B[bj].number is not None:
                cur = B[bj].number - A[ai].number
            k -= 1
        right[i] = cur
    return left, right


def align_matrix(A: list[Provision], B: list[Provision], S: list[list[float]], p: Params = DEFAULT) -> AlignmentResult:
    n, m = len(A), len(B)
    if n == 0 or m == 0:
        return AlignmentResult([], [x.eid for x in A], [x.eid for x in B])
    bg_a = [median(S[i]) for i in range(n)]
    bg_b = [median(S[i][j] for i in range(n)) for j in range(m)]
    anchors = _anchors(S, p)
    anchor_set = set(anchors)
    left, right = _offsets(A, B, anchors)
    W = [[0.0] * m for _ in range(n)]
    for i in range(n):
        pa = i / (n - 1) if n > 1 else 0.0
        for j in range(m):
            s = S[i][j]
            excess = s - max(bg_a[i], bg_b[j])
            num = 0.0
            if A[i].number is not None and B[j].number is not None and A[i].bis == B[j].bis:
                d = B[j].number - A[i].number
                num = 1.0 if d in (left[i], right[i]) else 0.0
            pb = j / (m - 1) if m > 1 else 0.0
            prior = 1.0 - abs(pa - pb)
            W[i][j] = p.w_sim * s + p.w_excess * excess + p.w_num * num + p.w_prior * prior - p.tau
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best = max(dp[i - 1][j], dp[i][j - 1])
            w = W[i - 1][j - 1]
            if w > 0:
                best = max(best, dp[i - 1][j - 1] + w)
            dp[i][j] = best
    pairs: list[Alignment] = []
    i, j = n, m
    while i > 0 and j > 0:
        w = W[i - 1][j - 1]
        if w > 0 and abs(dp[i][j] - (dp[i - 1][j - 1] + w)) < 1e-12:
            s = S[i - 1][j - 1]
            rival = max(max((S[i - 1][k] for k in range(m) if k != j - 1), default=0.0),
                        max((S[k][j - 1] for k in range(n) if k != i - 1), default=0.0))
            high = (i - 1, j - 1) in anchor_set or (w >= p.high_margin and s - rival >= p.ambiguity_margin)
            pairs.append(Alignment(A[i - 1].eid, B[j - 1].eid, round(s, 4), "high" if high else "low"))
            i, j = i - 1, j - 1
        elif abs(dp[i][j] - dp[i - 1][j]) < 1e-12:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    ma = {x.a_eid for x in pairs}
    mb = {x.b_eid for x in pairs}
    return AlignmentResult(pairs, [x.eid for x in A if x.eid not in ma], [x.eid for x in B if x.eid not in mb])


def align(a: Expression, b: Expression, p: Params = DEFAULT, **_ignored) -> AlignmentResult:
    A, B = a.articles(), b.articles()
    return align_matrix(A, B, similarity_matrix(A, B), p)
