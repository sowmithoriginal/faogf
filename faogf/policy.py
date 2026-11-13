"""Versioned declarative policy evaluation.

Semantics: deny-overrides, default deny, any evaluator error -> 'error'
(treated as non-permission by the gateway). Each published version is
recorded in the evidence store with a SUPERSEDES link.
A Cedar or OPA backend can replace `_evaluate` without changing the gateway.
"""
from dataclasses import dataclass, field
from .schema import now


@dataclass
class Decision:
    outcome: str            # permit | deny | error
    policy_id: str
    policy_version: int
    rule_id: str
    requires_approval: bool = False


@dataclass
class Policy:
    policy_id: str
    version: int
    rules: list = field(default_factory=list)


def _matches(rule, req):
    for key in ("tools", "actions", "agents"):
        if key in rule and req[key[:-1]] not in rule[key]:
            return False
    if rule.get("when_untrusted_context") and not req.get("untrusted_context"):
        return False
    if "recipient_domains" in rule:
        dom = str(req.get("args", {}).get("recipient", "")).split("@")[-1]
        if dom not in rule["recipient_domains"]:
            return False
    return True


class PolicyEngine:
    def __init__(self, store):
        self.store = store
        self.versions = {}   # (policy_id) -> list[Policy]

    def publish(self, policy: Policy):
        prior = self.versions.setdefault(policy.policy_id, [])
        supersedes = prior[-1].version if prior else None
        prior.append(policy)
        self.store.append("policy_version", {"policy_id": policy.policy_id, "version": policy.version,
                                             "rules": policy.rules, "supersedes": supersedes,
                                             "published_at": now()})

    def current(self, policy_id):
        return self.versions[policy_id][-1]

    def get(self, policy_id, version):
        return next(p for p in self.versions[policy_id] if p.version == version)

    def evaluate(self, policy: Policy, req: dict) -> Decision:
        try:
            return self._evaluate(policy, req)
        except Exception:  # fail closed
            return Decision("error", policy.policy_id, policy.version, "evaluator_error")

    @staticmethod
    def _evaluate(policy, req):
        permit, escalate = None, None
        for rule in policy.rules:
            if _matches(rule, req):
                if rule["effect"] == "deny":
                    return Decision("deny", policy.policy_id, policy.version, rule["id"])
                if rule["effect"] == "escalate":       # permitted only with human approval
                    escalate = escalate or rule
                    continue
                permit = permit or rule
        if permit:
            return Decision("permit", policy.policy_id, policy.version,
                            escalate["id"] if escalate else permit["id"],
                            permit.get("require_approval", False) or bool(escalate))
        return Decision("deny", policy.policy_id, policy.version, "default_deny")
