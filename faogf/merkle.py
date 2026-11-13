"""Epoch Merkle commitments over the evidence chain.

Every `epoch` records, the store's record hashes are committed to a Merkle root
that is anchored outside the operator's control (e.g. a timestamping service,
a transparency log, or a regulator inbox). This gives:
  * tamper evidence for full-suffix rewrites (which chain verification alone misses),
  * localisation of tampering to an epoch,
  * selective disclosure: an auditor can verify one record with an O(log n) proof
    without receiving the rest of the store.
"""
import hashlib


def _h(a, b):
    return hashlib.sha256((a + b).encode()).hexdigest()


def build_tree(leaves):
    levels = [list(leaves)]
    while len(levels[-1]) > 1:
        cur = levels[-1]
        if len(cur) % 2:
            cur = cur + [cur[-1]]
        levels.append([_h(cur[i], cur[i + 1]) for i in range(0, len(cur), 2)])
    return levels


def root(leaves):
    return build_tree(leaves)[-1][0]


def proof(levels, index):
    path = []
    for lvl in levels[:-1]:
        lvl = lvl + [lvl[-1]] if len(lvl) % 2 else lvl
        sib = index ^ 1
        path.append(("L" if sib < index else "R", lvl[sib]))
        index //= 2
    return path


def verify(leaf, path, expected_root):
    h = leaf
    for side, sib in path:
        h = _h(sib, h) if side == "L" else _h(h, sib)
    return h == expected_root


class EpochAnchors:
    def __init__(self, epoch=256):
        self.epoch = epoch
        self.roots = []          # anchored roots, one per complete or final partial epoch

    def commit(self, store):
        hashes = [r["hash"] for r in store.records]
        self.roots = [root(hashes[i:i + self.epoch]) for i in range(0, len(hashes), self.epoch)]
        return self.roots

    def prove(self, store, seq):
        e = seq // self.epoch
        leaves = [r["hash"] for r in store.records[e * self.epoch:(e + 1) * self.epoch]]
        return e, proof(build_tree(leaves), seq - e * self.epoch)

    def check(self, store):
        """Epoch indices whose recomputed root differs from the anchored root."""
        hashes = [r["hash"] for r in store.records]
        cur = [root(hashes[i:i + self.epoch]) for i in range(0, len(hashes), self.epoch)]
        n = max(len(cur), len(self.roots))
        return [i for i in range(n) if i >= len(cur) or i >= len(self.roots) or cur[i] != self.roots[i]]
