"""Score a fixed OpenAI classifier on frozen synthetic evidence through the repository verifier."""

import argparse
import json
from pathlib import Path

from ledgerlens.config import PROJECT_ROOT, get_chat_model, get_settings
from ledgerlens.verify.openai_classifier import PROMPT, EvidenceClassifier
from scripts.measure_heldout import score_fixed_classifier

MODEL = "openai:gpt-4.1-mini-2025-04-14"
OUTPUT = PROJECT_ROOT / "data/eval/report_openai_verifier.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    settings = get_settings()
    if settings.offline or not settings.openai_api_key:
        parser.error("This evaluation requires online mode and an OpenAI key.")
    classifier = EvidenceClassifier(get_chat_model(settings, model=MODEL, temperature=0))
    report = {"model": MODEL, "temperature": 0, "prompt": PROMPT, **score_fixed_classifier(classifier)}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"{report['correct']}/{report['total']} correct")


if __name__ == "__main__":
    main()
