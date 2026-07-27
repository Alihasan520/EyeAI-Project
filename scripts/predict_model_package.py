#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from eyeai.inference.run09_predictor import Run09Predictor


def main() -> None:
    parser = argparse.ArgumentParser(description="Run standalone inference from an EyeAI model package.")
    parser.add_argument("--model-package", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--device", default=None)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    predictor = Run09Predictor(args.model_package, device=args.device)
    payload = predictor.predict(args.image).to_dict()
    rendered = json.dumps(payload, indent=2, ensure_ascii=False)
    print(rendered)

    if args.output_json:
        output_path = Path(args.output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        print(f"Saved prediction: {output_path}")


if __name__ == "__main__":
    main()
