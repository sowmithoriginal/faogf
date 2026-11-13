"""Gateway-minted delegations.

Follows the delegation semantics of Mishra & Sharad (CIM: persistent
delegation id, lineage closure, binding to an authenticated principal) and the
narrowing rule (capability attenuation) described by Jeffs. FAOGF adopts these
rather than claiming them.
"""
from dataclasses import dataclass, field
from .schema import new_id, now


class NarrowingViolation(ValueError):
    pass


@dataclass
class Delegation:
    delegation_id: str
    principal_id: str
    agent_id: str
    tools: frozenset
    parent_id: str = None
    issued_at: float = field(default_factory=now)


class DelegationManager:
    def __init__(self, store):
        self.store = store
        self.by_id = {}
        self.revoked_at = {}

    def issue(self, principal_id, agent_id, tools, parent_id=None):
        tools = frozenset(tools)
        if parent_id:
            parent = self.by_id[parent_id]
            if not tools <= parent.tools:
                raise NarrowingViolation(f"{set(tools - parent.tools)} not held by parent {parent_id}")
            principal_id = parent.principal_id
        d = Delegation(new_id("del"), principal_id, agent_id, tools, parent_id)
        # record first: a delegation that cannot be recorded is never issued (fail closed)
        self.store.append("delegation_issued", {"delegation_id": d.delegation_id, "principal_id": principal_id,
                                                "agent_id": agent_id, "tools": sorted(tools),
                                                "parent_id": parent_id, "issued_at": d.issued_at})
        self.by_id[d.delegation_id] = d
        return d

    def revoke(self, delegation_id, actor="principal"):
        t = now()
        self.revoked_at[delegation_id] = t      # enforcement takes effect even if the record write is retried
        self.store.append("delegation_revoked", {"delegation_id": delegation_id, "at": t, "actor": actor})

    def lineage(self, delegation_id):
        chain, cur = [], self.by_id.get(delegation_id)
        while cur:
            chain.append(cur.delegation_id)
            cur = self.by_id.get(cur.parent_id) if cur.parent_id else None
        return chain  # leaf -> root

    def active(self, delegation_id, view=None):
        """`view` lets a lagging gateway use a stale snapshot of revocations."""
        revoked = self.revoked_at if view is None else view
        if delegation_id not in self.by_id:
            return False
        return not any(d in revoked for d in self.lineage(delegation_id))
