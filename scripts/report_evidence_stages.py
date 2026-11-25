#!/usr/bin/env python3
"""Audit policy passage IDs in the public replay catalogs without running the agent.

Candidate IDs are the policy tool's recorded results. Delivered IDs come from
tool messages in the last agent model input. Cited IDs come from the published
answer. These observations describe ID coverage, including gaps caused by trace
compaction. A target passage requires an independent reference for its case.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ledgerlens.observability.trace import ANSWER_KEY  # noqa: E402
from ledgerlens.observability.trace_event import TraceEvent  # noqa: E402
from ledgerlens.replay.bundle import EVENTS_FILE  # noqa: E402
from ledgerlens.tools.envelope import EVIDENCE_ID  # noqa: E402
from ledgerlens.verify.claims import _citations  # noqa: E402

CATALOGS = (ROOT / "site" / "replay", ROOT / "site" / "replay-real")
STAGES = ("candidate", "delivered", "cited")
POLICY_PREFIX = "policy:"
POLICY_TOOL = "search_policies"
MODEL_SPAN = "model"
INVESTIGATION_SPAN = "investigate"
SPAN_STARTED = "span.started"
SPAN_ENDED = "span.ended"
TOOL_MESSAGE = "tool"
NON_TOOL_MESSAGES = frozenset({"ai", "human", "system"})
INDEX_FILE = "index.json"
EVIDENCE_IDS_KEY = "evidence_ids"
SUCCESS_KEY = "ok"
UNPARSEABLE_TOOL_RESULT = "UNPARSEABLE_TOOL_RESULT"
COMPACTED_TEXT = re.compile(r"…\+\d+ chars$")
# The tool envelope puts its success flag and IDs before the potentially long data field.
ENVELOPE_PREFIX = re.compile(r'\{\s*"ok"\s*:\s*true\s*,\s*"evidence_ids"\s*:\s*')
DECODER = json.JSONDecoder()


def _policy_ids(ids: Iterable[str]) -> frozenset[str]:
    return frozenset(identifier for identifier in ids if identifier.startswith(POLICY_PREFIX))


@dataclass(frozen=True)
class Observation:
    """Visible IDs and whether the recording supports asserting absence."""

    ids: frozenset[str]
    complete: bool = True

    def contains(self, target: str) -> bool | None:
        """Return unknown if the target could be in an omitted part of the trace."""
        if target in self.ids:
            return True
        return False if self.complete else None


@dataclass(frozen=True)
class EvidenceStages:
    """The observed policy IDs at each stage of one recorded answer."""

    candidate: Observation | None
    delivered: Observation | None
    cited: Observation | None

    def outcome_for(self, target: str) -> str:
        """Find the first observed loss for a passage specified by a reference."""
        for stage, outcome in zip(STAGES, ("missing_candidate", "candidate_dropped", "delivered_uncited"), strict=True):
            observation = getattr(self, stage)
            present = None if observation is None else observation.contains(target)
            if present is None:
                return "unknown"
            if not present:
                return outcome
        return "cited"

    @property
    def candidate_dropped(self) -> list[str] | None:
        """List candidate IDs absent from a fully observed model input."""
        return _lost_ids(self.candidate, self.delivered)

    @property
    def delivered_uncited(self) -> list[str] | None:
        """List delivered IDs absent from a fully observed answer."""
        return _lost_ids(self.delivered, self.cited)


def _lost_ids(before: Observation | None, after: Observation | None) -> list[str] | None:
    if before is None or after is None or not before.complete or not after.complete:
        return None
    return sorted(before.ids - after.ids)


def _envelope_ids(output: object) -> Observation | None:
    if not isinstance(output, dict):
        return None
    if output.get(SUCCESS_KEY) is False:
        failure = output.get("error")
        code = failure.get("code") if isinstance(failure, dict) else None
        if not isinstance(code, str) or not code or code == UNPARSEABLE_TOOL_RESULT:
            return None
        return Observation(frozenset())
    ids = output.get(EVIDENCE_IDS_KEY)
    if output.get(SUCCESS_KEY) is True and isinstance(ids, list):
        valid = [item for item in ids if isinstance(item, str) and EVIDENCE_ID.fullmatch(item)]
        complete = len(valid) == len(ids)
        visible = _policy_ids(valid)
        return Observation(visible, complete) if complete or visible else None
    return None


def _tool_message_ids(content: object) -> Observation | None:
    if not isinstance(content, str):
        return None
    try:
        return _envelope_ids(json.loads(content))
    except json.JSONDecodeError:
        prefix = ENVELOPE_PREFIX.match(content)
        if prefix is None or COMPACTED_TEXT.search(content) is None:
            return None
        try:
            ids, _ = DECODER.raw_decode(content, prefix.end())
        except json.JSONDecodeError:
            return None
        # The entire ID array is visible even though the later passage text was cut.
        return _envelope_ids({SUCCESS_KEY: True, EVIDENCE_IDS_KEY: ids})


def _aggregate(observations: Iterable[Observation | None]) -> Observation | None:
    parts = list(observations)
    ids = frozenset(identifier for part in parts if part for identifier in part.ids)
    complete = bool(parts) and all(part is not None and part.complete for part in parts)
    return Observation(ids, complete) if complete or ids else None


def _model_ids(inputs: object) -> Observation | None:
    if not isinstance(inputs, dict) or not isinstance(messages := inputs.get("messages"), list):
        return None
    if not messages:
        return Observation(frozenset())
    observations = []
    for message in messages:
        message_type = message.get("type") if isinstance(message, dict) else None
        if message_type == TOOL_MESSAGE:
            observations.append(_tool_message_ids(message.get("content")))
        elif isinstance(message_type, str) and message_type in NON_TOOL_MESSAGES:
            observations.append(Observation(frozenset()))
        else:
            observations.append(None)
    return _aggregate(observations)


def _answer_ids(outputs: object) -> Observation | None:
    if not isinstance(outputs, dict) or not isinstance(answer := outputs.get(ANSWER_KEY), str):
        return None
    ids = _policy_ids(_citations(answer)[1])
    complete = COMPACTED_TEXT.search(answer) is None
    return Observation(ids, complete) if complete or ids else None


def observe_stages(events: Iterable[TraceEvent]) -> EvidenceStages:
    """Extract observations from one run in recorded event order."""
    searches = {}
    delivered = cited = None
    for event in events:
        payload = event.payload
        name = payload.get("name")
        if name == POLICY_TOOL and event.event_type == SPAN_STARTED:
            searches[event.span_id or event.seq] = None
        elif name == POLICY_TOOL and event.event_type == SPAN_ENDED:
            searches[event.span_id or event.seq] = _envelope_ids(payload.get("outputs"))
        elif name == MODEL_SPAN and event.event_type == SPAN_STARTED:
            delivered = _model_ids(payload.get("inputs"))
        elif name == INVESTIGATION_SPAN and event.event_type == SPAN_ENDED:
            cited = _answer_ids(payload.get("outputs"))
    return EvidenceStages(_aggregate(searches.values()), delivered, cited)


def _catalog_report(catalog: Path) -> dict:
    coverage = {stage: dict(complete=0, partial=0, unknown=0) for stage in STAGES}
    runs = []
    for entry in json.loads((catalog / INDEX_FILE).read_text(encoding="utf-8")):
        path = catalog / entry["bundle_path"] / EVENTS_FILE
        stages = observe_stages(
            TraceEvent.from_dict(json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines()
        )
        run = {"id": entry["id"], "capture_kind": entry["capture_kind"]}
        for stage in STAGES:
            observation = getattr(stages, stage)
            if observation is None:
                coverage[stage]["unknown"] += 1
                run[stage] = None
            else:
                coverage[stage]["complete" if observation.complete else "partial"] += 1
                run[stage] = {"ids": sorted(observation.ids), "complete": observation.complete}
        run["candidate_dropped"] = stages.candidate_dropped
        run["delivered_uncited"] = stages.delivered_uncited
        runs.append(run)
    return {"catalog": catalog.name, "run_count": len(runs), "coverage": coverage, "runs": runs}


def main(argv: Sequence[str] | None = None) -> int:
    """Write evidence observations and coverage to stdout as JSON."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path, nargs="*", help="published replay catalog directory")
    catalogs = parser.parse_args(argv).catalog or CATALOGS
    print(json.dumps([_catalog_report(catalog) for catalog in catalogs], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
