"""The verdict of a published bundle, read back out of the bundle and checked again with the code of the repository.

Why it exists: a published bundle shows a verdict ("CL1 supported") and the evidence that verdict was computed
from. A reader of the bundle has to be able to redo the verdict with the evidence the bundle publishes, because
a verdict nobody can redo is a claim nobody can check. This module rebuilds the result of the run out of the
published events and hands it to the verifier of the repository, so that the label the bundle publishes and the
label the code gives can be compared.

How the result is rebuilt: the answer, the recommendation and the question come from the span of the
investigation, and the evidence comes from the spans of the tools. The content and the reference of each
evidence are written the way the integrator writes them, and they are read from the integrator for that reason:
a reconstruction that writes the evidence its own way would drift from the recording and would report a
difference that is not there. The claims are not read from the bundle, because the bundle does not publish the
text of a claim: they are extracted from the published answer and the published evidence, exactly as the run
did, so the check runs on the claims of the recording and not on claims of another shape.

What it proves and what it does not: it proves that the published label is the label the code gives for the
published evidence. It does not prove that the evidence is the truth of the ledger: that is the digest of the
snapshot, which the manifest of the bundle carries and which the artifact of the ledger repeats.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from ledgerlens.agents.integrator import _SOURCE_BY_PREFIX, _content, _ref
from ledgerlens.replay.bundle import EVENTS_FILE
from ledgerlens.schemas import Coherence, Evidence, InvestigationResult
from ledgerlens.verify.checks import verify_result

__all__ = [
    "differences",
    "memory_snapshot_differences",
    "published_labels",
    "published_result",
    "reverified_labels",
]

# The name of a claim of a recording, the identifier the bundle publishes the label under.
_CLAIM_NAME = re.compile(r"^CL\d+$")

# The span of the investigation, the one that holds the answer and the recommendation of the run.
_INVESTIGATION = "investigate"

# The span of the verifier, the one that holds the answer the run verified.
#
# Why the rebuild reads the answer from there and not from the span of the investigation: the escalation adds a
# notice to the answer after the verification, and that notice was never a claim of the run. The claims were
# extracted from the text the verifier received, so the rebuild has to read that same text (ADR-077).
_VERIFIER = "verify"

# The span of a tool of the agent, the one that holds the evidence of the run.
_TOOL = "tool"

# The actions the result may carry. The bundle of a run that names another one names a run of another shape,
# and the shape is not what this module checks, so the action falls back to the one that changes nothing.
_ACTIONS = frozenset(
    {
        "none",
        "explain_to_customer",
        "issue_refund",
        "reject_refund",
        "submit_chargeback_evidence",
        "escalate_to_human",
        "ask_for_clarification",
    }
)


def _recorded_events(bundle_dir: Path) -> list[dict[str, Any]]:
    """The recorded events of a bundle, parsed as they were recorded.

    Why the recorded text and not the event the core re-derives: a re-derivation would coerce a wrong type
    into a right one, and the check would run on an event the bundle never had.
    """
    text = (bundle_dir / EVENTS_FILE).read_text(encoding="utf-8")
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            events.append(payload)
    return events


def _payload_of(event: dict[str, Any]) -> dict[str, Any]:
    """The payload of an event, or an empty one when it has none."""
    payload = event.get("payload")
    return payload if isinstance(payload, dict) else {}


def _moment_of(event: dict[str, Any]) -> datetime:
    """The moment of an event, as the recording wrote it."""
    try:
        return datetime.fromisoformat(str(event.get("at")))
    except ValueError:
        return datetime.fromtimestamp(0)


def _tool_calls(events: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any], str, datetime]]:
    """The calls of the tools of the recording: the arguments, what the tool returned, the name and the moment.

    The arguments of the call and its answer live in two events, the start and the end of the same span, and
    they are paired by the identifier of the span.
    """
    arguments: dict[str, dict[str, Any]] = {}
    calls: list[tuple[dict[str, Any], dict[str, Any], str, datetime]] = []
    for event in events:
        payload = _payload_of(event)
        name = str(payload.get("name") or "")
        span_id = str(event.get("span_id") or "")
        if payload.get("run_type") != _TOOL:
            continue
        if event.get("event_type") == "span.started":
            inputs = payload.get("inputs")
            arguments[span_id] = inputs if isinstance(inputs, dict) else {}
        elif event.get("event_type") == "span.ended":
            outputs = payload.get("outputs")
            calls.append(
                (arguments.get(span_id, {}), outputs if isinstance(outputs, dict) else {}, name, _moment_of(event))
            )
    return calls


def _evidence_of(
    arguments: dict[str, Any], outputs: dict[str, Any], name: str, moment: datetime
) -> list[Evidence]:
    """The evidence one call of a tool produced, in the shape the integrator writes it.

    The content and the reference come from the integrator, because the content of the evidence is the premise
    the verifier reads: a reconstruction that writes it its own way would not be the evidence of the recording.
    """
    if not outputs.get("ok"):
        return []
    data = outputs.get("data")
    data = data if isinstance(data, dict) else {}
    evidence: list[Evidence] = []
    for evidence_id in outputs.get("evidence_ids") or []:
        identifier = str(evidence_id)
        source_type = _SOURCE_BY_PREFIX.get(identifier.split(":", 1)[0])
        if source_type is None:
            continue
        evidence.append(
            Evidence(
                id=identifier,
                source_type=source_type,
                tool=name,
                content=_content(name, identifier, data),
                ref=_ref(name, identifier, data, arguments),
                retrieved_at=moment,
            )
        )
    return evidence


def published_result(bundle_dir: Path) -> InvestigationResult:
    """The result of the run, rebuilt from what the bundle publishes.

    The claims are left empty on purpose: the verifier extracts them from the answer and the evidence, exactly
    as the run did, so the check runs on the claims of the recording.

    The answer is the one the run verified, which the bundle publishes in the span of the verifier. The final answer
    of the investigation carries the notice of the escalation, and that notice was never a claim of the run, so a
    rebuild that used it would find claims the run never had (ADR-077). A recording without a span of the verifier
    falls back to the final answer, because it has no claims to rebuild and no text to rebuild them from.
    """
    events = _recorded_events(bundle_dir)
    answer = ""
    verified_answer = ""
    question = ""
    recommended_action = "none"
    requires_human_review = False
    evidence: list[Evidence] = []
    seen: set[str] = set()

    for event in events:
        payload = _payload_of(event)
        name = str(payload.get("name") or "")
        if event.get("event_type") == "span.started":
            inputs = payload.get("inputs")
            inputs = inputs if isinstance(inputs, dict) else {}
            if name == _INVESTIGATION:
                question = str(inputs.get("question") or "")
            if name == _VERIFIER:
                verified_answer = str(inputs.get("answer") or "")
        if event.get("event_type") != "span.ended":
            continue
        outputs = payload.get("outputs")
        outputs = outputs if isinstance(outputs, dict) else {}
        if name == _INVESTIGATION:
            answer = str(outputs.get("answer") or answer)
            action = str(outputs.get("recommended_action") or "")
            recommended_action = action if action in _ACTIONS else "none"
            requires_human_review = bool(outputs.get("requires_human_review"))

    for arguments, outputs, name, moment in _tool_calls(events):
        for item in _evidence_of(arguments, outputs, name, moment):
            if item.id not in seen:
                seen.add(item.id)
                evidence.append(item)

    return InvestigationResult(
        session_id=str(events[0].get("run_id") or "") if events else "",
        question=question,
        answer=verified_answer or answer,
        claims=[],
        evidence=evidence,
        verdicts=[],
        coherence=Coherence(passed=True),
        recommended_action=recommended_action,
        requires_human_review=requires_human_review,
    )


def published_labels(bundle_dir: Path) -> dict[str, str]:
    """The label the bundle publishes for each claim, in the order of the claims.

    The label is read from the span of the verifier of the claim, which is where the run wrote it.
    """
    labels: dict[str, str] = {}
    for event in _recorded_events(bundle_dir):
        payload = _payload_of(event)
        name = str(payload.get("name") or "")
        if not _CLAIM_NAME.match(name) or event.get("event_type") != "span.ended":
            continue
        outputs = payload.get("outputs")
        if isinstance(outputs, dict) and outputs.get("label"):
            labels[name] = str(outputs["label"])
    return labels


def reverified_labels(bundle_dir: Path) -> dict[str, str]:
    """The label the code of the repository gives for the published evidence of the bundle.

    The verifier runs offline, with the stand-in of the NLI model, which is the model the capture ran with: the
    capture is deterministic and calls no model.
    """
    verified = verify_result(published_result(bundle_dir))
    return {verdict.claim_id: verdict.label for verdict in verified.verdicts}


def differences(bundle_dir: Path) -> list[str]:
    """The differences between the published labels and the labels the code gives, one line each.

    The line names the claim and both labels, so the reader of the failure sees which verdict is unreachable
    and not only that something is unreachable.
    """
    published = published_labels(bundle_dir)
    reverified = reverified_labels(bundle_dir)
    lines: list[str] = []
    for claim_id in sorted(set(published) | set(reverified)):
        left = published.get(claim_id, "no label")
        right = reverified.get(claim_id, "no label")
        if left != right:
            lines.append(f"{claim_id}: the bundle publishes {left} and the code gives {right}")
    return lines


def memory_snapshot_differences(bundle_dir: Path) -> list[str]:
    """The differences of the snapshot of the memory of the run, when the bundle names one.

    Why the check exists: a replay of an old case reads the memory of its generation, and the digest of the
    snapshot of the memory travels in the manifest of the bundle. A bundle whose snapshot does not match the
    digest it names is a bundle that asks the reader to trust the name and not the bytes, and the verifier
    refuses it. A bundle that names no snapshot of the memory is a bundle of the versions before the snapshot
    existed, and it is checked as it always was.
    """
    import hashlib

    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared = manifest.get("memory_snapshot_sha256")
    if not declared:
        return []
    snapshot_path = bundle_dir / "memory_snapshot.json"
    if not snapshot_path.is_file():
        return [f"the manifest names the snapshot of the memory {declared} and the file of it is not in the bundle"]
    digest = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    if digest != declared:
        return [
            f"the snapshot of the memory of the bundle has the digest {digest} and the manifest names {declared}"
        ]
    return []
