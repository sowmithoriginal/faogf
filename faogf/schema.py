"""FAOGF attribute vocabulary.

Reuses OpenTelemetry GenAI semantic-convention attributes where they exist
(gen_ai.*) and places every FAOGF addition under the fin.audit.* namespace.
NOTE: the gen_ai.* conventions are still evolving; pin the semconv version you
cite in the paper and re-check these names against it.
"""
import hashlib
import json
import time
import uuid

SEMCONV_NOTE = "gen_ai.* names per OpenTelemetry GenAI semantic conventions (development status); verify against pinned version"

# --- OpenTelemetry GenAI semantic conventions (reused, not owned by FAOGF)
GENAI_OPERATION = "gen_ai.operation.name"      # chat | execute_tool | invoke_agent
GENAI_TOOL_NAME = "gen_ai.tool.name"
GENAI_TOOL_CALL_ID = "gen_ai.tool.call.id"
GENAI_TOOL_ARGS = "gen_ai.tool.call.arguments"  # opt-in in semconv; enabled for baselines
GENAI_AGENT_ID = "gen_ai.agent.id"
GENAI_TOOL_RESULT = "gen_ai.tool.call.result"      # opt-in content capture (used only by content-logging baselines)
GENAI_INPUT_MESSAGES = "gen_ai.input.messages"     # opt-in content capture (used only by content-logging baselines)
GENAI_AGENT_NAME = "gen_ai.agent.name"
GENAI_MODEL = "gen_ai.request.model"

# --- FAOGF extensions (proposed namespace)
PRINCIPAL = "fin.audit.principal.id"
DELEGATION = "fin.audit.delegation.id"
DELEGATION_PARENT = "fin.audit.delegation.parent_id"
ACTION = "fin.audit.action"                    # read | search | compute | delegate | share | generate
RESOURCES = "fin.audit.resource.ids"
POLICY_ID = "fin.audit.policy.id"
POLICY_VERSION = "fin.audit.policy.version"
POLICY_DECISION = "fin.audit.policy.decision"  # permit | deny | error
POLICY_RULE = "fin.audit.policy.rule_id"
APPROVAL = "fin.audit.approval.status"         # not_required | granted | denied
EVIDENCE_IDS = "fin.audit.evidence.ids"        # evidence produced (tool) or in context (chat)
RECORD_ID = "fin.audit.record.id"              # pointer into the evidence store
RECORD_STATUS = "fin.audit.record.status"      # recorded | unrecorded
BINDING = "fin.audit.binding"
EVIDENCE_SOURCES = "fin.audit.evidence.sources"  # "source_id@version#sha256[:16]|trust_class"
MODEL_CALL = "fin.audit.model_call.id"         # model call whose output requested this tool call
DERIVED_FROM = "fin.audit.decision.derived_from"                  # gateway | unbound

DELEGATION_KEYS = {PRINCIPAL, DELEGATION, DELEGATION_PARENT}


def now() -> float:
    return time.time()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
