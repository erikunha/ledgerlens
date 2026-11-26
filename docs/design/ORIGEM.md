# Provenance of the v3 package

This folder is a versioned copy of the LedgerLens v3 design package. It is not the source of truth of the code: the code is the source of truth. The package is the plan, and the plan enters the repository so that the code and the plan can be read and reviewed in the same tree.

## Origin

- Origin: the v3 design package, which lives outside git by the rule of the repository conventions.
- Imported at: 2026-11-11T20:15:33+00:00
- Files: 125
- sha256 of the source set: `4bf1cb2402ac7b31d85244e9ec7e4970c1db5ab63f17361d43471e102a2cbad1`
- sha256 of the converted tree: `17991f6f6daf3657d1a40a5dfe1316c475b1cbb6bbe8ae595d4e5b287cae04f5`
- Reimport command: `uv run python scripts/import_v3_pack.py --source <package folder>`
- Check command: `uv run python scripts/import_v3_pack.py --source <package folder> --check`

The source sha256 is calculated over the package: for each file, in path order, the relative path
followed by the bytes. The converted tree sha256 is the same calculation over the files that stayed
versioned, so any clone can check it.

## What was converted

The conversion is mechanical and lives in the import script. Nothing else was edited.

- Em dash (U+2014) and en dash (U+2013) became a hyphen with spaces. A number range stays glued, for example `1-15`.
- The English word for evaluation criteria, and its plural, became `evaluation criteria`, because the context guard of the repository forbids that word.
- The cedilla of `facade` was dropped, because the repository guard reads a cedilla as a Portuguese letter.
- The two documents that exist only in Brazilian Portuguese were translated into English and renamed. The translation lives in the import script, so the import stays reproducible.

## What was not converted

- The content. No claim of the package was corrected, expanded or deleted.
- The ids. The package has its own id space, defined in the PRD that comes here, so the reference does not dangle. The context guard of the repository exempts this folder by path, only for the ids.

## How this relates to the plan that drives the work

`docs/roadmap-v3.md` is the plan, in the voice of the repository, with the table of slices. This folder is the source material. When the two diverge, what counts is the plan of `docs/roadmap-v3.md` and what binds is the code.

## Inventory

| File | Bytes |
|---|---|
| `00-READ-ME-FIRST.md` | 4173 |
| `AGENTS.md` | 3668 |
| `README.md` | 9486 |
| `adrs/ADR-P001-preserve-python-core.md` | 893 |
| `adrs/ADR-P002-replay-truthfulness.md` | 809 |
| `adrs/ADR-P003-sandbox-events.md` | 945 |
| `adrs/ADR-P004-byok-ephemeral.md` | 894 |
| `adrs/ADR-P005-sse-trace-protocol.md` | 876 |
| `adrs/ADR-P006-eval-governance.md` | 876 |
| `adrs/ADR-P007-no-multiagent-by-default.md` | 734 |
| `adrs/ADR-P008-portfolio-deployment.md` | 770 |
| `adrs/ADR-P009-privacy-scope.md` | 910 |
| `adrs/README.md` | 1248 |
| `advanced-specs/R1-02-cold-start-guided-replay.md` | 2551 |
| `advanced-specs/R10-03-human-review-queue-simulator.md` | 2207 |
| `advanced-specs/R10-06-human-approval-state-machine.md` | 1975 |
| `advanced-specs/R11-02-budgeted-specialist-dispatch.md` | 2087 |
| `advanced-specs/R11-05-graph-checkpoint-and-resume.md` | 1932 |
| `advanced-specs/R12-04-versioned-memory-with-poisoning-quarantine.md` | 2158 |
| `advanced-specs/R13-02-safe-adversarial-laboratory.md` | 2129 |
| `advanced-specs/R15-02-model-router-with-budgeted-fallback.md` | 2099 |
| `advanced-specs/R16-02-idempotent-durable-operations-and-forensic-traces.md` | 2055 |
| `advanced-specs/R17-04-operations-digital-twin-simulation.md` | 2025 |
| `advanced-specs/R18-02-source-grounded-document-extraction.md` | 1954 |
| `advanced-specs/R19-02-causal-counterfactual-interventions.md` | 2010 |
| `advanced-specs/R2-03-isolated-sandbox-mutations.md` | 2302 |
| `advanced-specs/R20-01-verified-feedback-to-evaluation-and-training.md` | 1967 |
| `advanced-specs/R22-01-portable-proof-of-work-artifact-export.md` | 2277 |
| `advanced-specs/R4-04-paired-evaluation-arena.md` | 2195 |
| `advanced-specs/R8-02-evidence-graph-and-provenance.md` | 2267 |
| `advanced-specs/R9-03-cost-per-correctly-resolved-case.md` | 2291 |
| `advanced-specs/R9-06-risk-weighted-decision-utility.md` | 2003 |
| `ai/00-AGENTIC-PLATFORM-VISION.md` | 2628 |
| `ai/01-MULTIAGENT-ORCHESTRATION.md` | 5689 |
| `ai/02-SPECIALIST-ROSTER.md` | 4629 |
| `ai/03-MODEL-GATEWAY-ROUTING.md` | 2996 |
| `ai/04-MEMORY-RETRIEVAL-AND-KNOWLEDGE.md` | 2762 |
| `ai/05-EVALUATION-RESEARCH.md` | 3636 |
| `ai/06-THREAT-AND-ADVERSARIAL-LAB.md` | 3320 |
| `ai/07-REVIEW-MEMORY-LEARNING.md` | 2195 |
| `ai/08-RESEARCH-HORIZONS-2030.md` | 3989 |
| `ai/CAPABILITY-ATLAS.md` | 21764 |
| `ai/capability-atlas.json` | 67174 |
| `contracts/examples/live-run-request.json` | 406 |
| `contracts/examples/model-profile.json` | 422 |
| `contracts/examples/public-investigation-result.json` | 1105 |
| `contracts/examples/replay-bundle-example.json` | 2119 |
| `contracts/examples/sandbox-fault-mutation.json` | 150 |
| `contracts/examples/trace-event.json` | 383 |
| `contracts/examples/v3-agent-plan.json` | 1007 |
| `contracts/examples/v3-decision-record.json` | 634 |
| `contracts/examples/v3-economic-run.json` | 752 |
| `contracts/examples/v3-evidence-ref.json` | 425 |
| `contracts/examples/v3-experiment-manifest.json` | 770 |
| `contracts/examples/v3-portfolio-proof.json` | 631 |
| `contracts/examples/v3-review-task.json` | 472 |
| `contracts/openapi-v3-extension.yaml` | 6393 |
| `contracts/openapi.yaml` | 13116 |
| `contracts/schemas/live-run-request.schema.json` | 2290 |
| `contracts/schemas/model-profile.schema.json` | 2096 |
| `contracts/schemas/public-investigation-result.schema.json` | 4581 |
| `contracts/schemas/replay-bundle.schema.json` | 1629 |
| `contracts/schemas/scenario-mutation.schema.json` | 4452 |
| `contracts/schemas/trace-event.schema.json` | 1455 |
| `contracts/schemas/v3-agent-plan.schema.json` | 2934 |
| `contracts/schemas/v3-decision-record.schema.json` | 1525 |
| `contracts/schemas/v3-economic-run.schema.json` | 3562 |
| `contracts/schemas/v3-evidence-ref.schema.json` | 1433 |
| `contracts/schemas/v3-experiment-manifest.schema.json` | 2025 |
| `contracts/schemas/v3-portfolio-proof.schema.json` | 2084 |
| `contracts/schemas/v3-review-task.schema.json` | 1644 |
| `design/SCREEN-WIREFRAMES.md` | 5489 |
| `docs/00-EXECUTIVE-SUMMARY.md` | 4322 |
| `docs/01-REPOSITORY-AUDIT.md` | 7850 |
| `docs/02-PRD-AND-DEFINITION-OF-DONE.md` | 7677 |
| `docs/03-EXPERIENCE-AND-SCREENS.md` | 10335 |
| `docs/04-SCENARIO-AND-SIMULATION-ENGINE.md` | 9236 |
| `docs/05-SYSTEM-ARCHITECTURE.md` | 8396 |
| `docs/06-AGENT-RUNTIME-AND-TOOLING.md` | 8808 |
| `docs/07-BYOK-MODEL-REGISTRY.md` | 6387 |
| `docs/08-EVIDENCE-TRACING-AND-PROVENANCE.md` | 5763 |
| `docs/09-EVALUATION-AND-EXPERIMENTS.md` | 8083 |
| `docs/10-SECURITY-AND-THREAT-MODEL.md` | 6121 |
| `docs/11-API-AND-INTERFACE-CONTRACTS.md` | 5217 |
| `docs/12-FRONTEND-ENGINEERING-AND-DESIGN-SYSTEM.md` | 6613 |
| `docs/13-CI-CD-DEPLOYMENT-AND-RUNBOOKS.md` | 5682 |
| `docs/14-PORTFOLIO-PRESENTATION.md` | 4386 |
| `docs/15-RISKS-AND-OPEN-DECISIONS.md` | 3616 |
| `docs/16-SOURCES.md` | 3300 |
| `docs/17-IMPLEMENTATION-HANDOFF.md` | 3567 |
| `eval/TEST-MATRIX.md` | 2850 |
| `product/01-SCREEN-REGISTRY.md` | 32554 |
| `product/02-MODES-AND-USER-JOURNEYS.md` | 2311 |
| `product/03-SCENARIOS-AND-EXPERIMENTS.md` | 4721 |
| `product/04-PORTFOLIO-NARRATIVES.md` | 2678 |
| `product/05-GUIDED-LEARNING-TOURS.md` | 2045 |
| `product/screen-registry.json` | 13517 |
| `research/01-WHAT-CHANGED-IN-2026.md` | 4019 |
| `research/02-PUBLIC-TOOLS-AND-REFERENCE-COMPARISON.md` | 3099 |
| `research/03-RESEARCH-INTAKE-TEMPLATE.md` | 1712 |
| `roadmap/90-DAY-EXECUTION.md` | 3167 |
| `roadmap/IMPLEMENTATION-BACKLOG-V3.md` | 20628 |
| `roadmap/IMPLEMENTATION-BACKLOG.md` | 5287 |
| `roadmap/RELEASE-TRAIN-2027-2030.md` | 16066 |
| `roadmap/RELEASE-TRAIN.md` | 4487 |
| `roadmap/implementation-backlog-v3.json` | 46674 |
| `roadmap/release-train.json` | 10424 |
| `specs/LL-R0-03-trace-event-transport.md` | 4202 |
| `specs/LL-R1-04-guided-replay.md` | 2850 |
| `specs/LL-R2-02-isolated-sandbox.md` | 3820 |
| `specs/LL-R3-02-ephemeral-byok.md` | 3337 |
| `specs/LL-R4-03-verifier-eval-reconciliation.md` | 3336 |
| `strategy/00-STRATEGIC-INTELLIGENCE-STACK.md` | 5866 |
| `strategy/01-MARKET-AND-VALUE-FLOW.md` | 4377 |
| `strategy/02-BOTTLENECKS-AND-INCENTIVES.md` | 2945 |
| `strategy/03-CAREER-LEVERAGE-AND-DISTRIBUTION.md` | 3762 |
| `strategy/04-RISK-OPTIONALITY-DECISION-JOURNAL.md` | 2527 |
| `strategy/05-ECONOMIC-MODELS.md` | 4148 |
| `verification/FILE-MANIFEST-v3.json` | 21478 |
| `verification/FILE-MANIFEST.json` | 10166 |
| `verification/VALIDATION-v3.md` | 2238 |
| `verification/VALIDATION.md` | 2090 |
| `verification/generate_contracts.py` | 18154 |
| `verification/package.py` | 3507 |
| `verification/validate.py` | 3401 |
