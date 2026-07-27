from __future__ import annotations

import argparse
import json
from pathlib import Path

from huggingface_hub import snapshot_download


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download EyeAI local language models.")
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--chat-model",
        default="Qwen/Qwen3-4B-Instruct-2507",
    )
    parser.add_argument(
        "--embedding-model",
        default="Qwen/Qwen3-Embedding-0.6B",
    )
    parser.add_argument("--token", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    chat_dir = args.output_root / "qwen3_4b_instruct_2507"
    embedding_dir = args.output_root / "qwen3_embedding_0_6b"

    snapshot_download(
        repo_id=args.chat_model,
        local_dir=chat_dir,
        token=args.token,
    )
    snapshot_download(
        repo_id=args.embedding_model,
        local_dir=embedding_dir,
        token=args.token,
    )
    manifest = {
        "chat_model": args.chat_model,
        "chat_model_dir": str(chat_dir),
        "embedding_model": args.embedding_model,
        "embedding_model_dir": str(embedding_dir),
    }
    (args.output_root / "language_models_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
