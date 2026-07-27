#!/usr/bin/env python
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

from eyeai.inference.model_package import export_model_package


def current_git_commit(repo_dir: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the frozen Run 09 + TTA model package.")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--package-config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tta-summary")
    parser.add_argument("--training-summary")
    parser.add_argument("--training-config")
    parser.add_argument("--repo-dir", default=".")
    args = parser.parse_args()

    output_dir = export_model_package(
        trained_checkpoint=args.checkpoint,
        package_config_path=args.package_config,
        output_dir=args.output_dir,
        tta_summary_path=args.tta_summary,
        training_summary_path=args.training_summary,
        source_training_config_path=args.training_config,
        source_git_commit=current_git_commit(Path(args.repo_dir)),
    )
    print(f"Model package created: {output_dir}")
    for path in sorted(output_dir.rglob("*")):
        if path.is_file():
            print(f"- {path.relative_to(output_dir)} ({path.stat().st_size / (1024 ** 2):.2f} MB)")


if __name__ == "__main__":
    main()
