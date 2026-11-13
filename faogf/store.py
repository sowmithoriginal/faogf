"""Append-only, hash-chained evidence store.

This is the synchronous 'record of record' path. OTel spans are the
asynchronous, best-effort path. Tamper evidence comes from the hash chain,
not from span links.
"""
import json
from .schema import canonical, now, sha256

GENESIS = "0" * 64


class StoreUnavailable(IOError):
    pass


class EvidenceStore:
    def __init__(self, path=None):
        self.records = []
        self.path = path
        self._prev = GENESIS
        self.fail_rate = 0.0          # fault injection: probability a write fails
        self._rng = None
        if path:
            open(path, "w").close()

    def set_faults(self, fail_rate, rng):
        self.fail_rate, self._rng = fail_rate, rng

    def append(self, kind: str, body: dict) -> dict:
        if self.fail_rate and self._rng.random() < self.fail_rate:
            raise StoreUnavailable("evidence store write failed")
        rec = {"seq": len(self.records), "kind": kind, "ts": now(), "body": body, "prev": self._prev}
        rec["hash"] = sha256(canonical(rec))
        self.records.append(rec)
        self._prev = rec["hash"]
        if self.path:
            with open(self.path, "a") as f:
                f.write(json.dumps(rec) + "\n")
        return rec

    def verify(self):
        """Return seq numbers whose hash or chain link does not verify."""
        bad, prev = [], GENESIS
        for r in self.records:
            body = {k: r[k] for k in ("seq", "kind", "ts", "body", "prev")}
            if r["prev"] != prev or sha256(canonical(body)) != r["hash"]:
                bad.append(r["seq"])
            prev = r["hash"]
        return bad

    def of(self, kind):
        return [r for r in self.records if r["kind"] == kind]

    def size_bytes(self):
        return sum(len(json.dumps(r)) for r in self.records)


class SpooledStore:
    """Central store with a local write-ahead spool used when the central store is
    unavailable (e.g. a network or service outage). Each has its own hash chain;
    spooled records are forwarded on recovery. Assumes the spool's failure is
    independent of the central store's (local disk vs. remote service)."""

    def __init__(self, central, spool):
        self.central, self.spool = central, spool
        self.spooled = 0

    def append(self, kind, body):
        try:
            return self.central.append(kind, body)
        except StoreUnavailable:
            rec = self.spool.append(kind, body)      # raises if the spool also fails -> caller fails closed
            self.spooled += 1
            return rec

    def set_faults(self, fail_rate, rng):
        self.central.set_faults(fail_rate, rng)

    @property
    def fail_rate(self):
        return self.central.fail_rate

    @fail_rate.setter
    def fail_rate(self, v):
        self.central.fail_rate = v

    @property
    def records(self):
        return sorted(self.central.records + self.spool.records, key=lambda r: r["ts"])

    def of(self, kind):
        return [r for r in self.records if r["kind"] == kind]

    def verify(self):
        return self.central.verify() + [("spool", s) for s in self.spool.verify()]

    def size_bytes(self):
        return self.central.size_bytes() + self.spool.size_bytes()
