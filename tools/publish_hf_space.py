from __future__ import annotations

import os

from huggingface_hub import HfApi


def main() -> None:
    token = os.environ.get("HF_TOKEN", "")
    source_sha = os.environ.get("GITHUB_SHA", "")
    if not token:
        raise RuntimeError("HF_TOKEN non configurato.")
    HfApi(token=token).upload_folder(
        repo_id="Sibucs/Familiarizzap",
        repo_type="space",
        folder_path="space",
        commit_message=f"Pubblicato da GitHub: {source_sha[:7]}",
    )


if __name__ == "__main__":
    main()
