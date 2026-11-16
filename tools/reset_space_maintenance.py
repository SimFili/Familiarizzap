from __future__ import annotations

import os

from huggingface_hub import HfApi


SPACE_REPO_ID = "Sibucs/Familiarizzap"
SECRET_NAME = "DATA_CLEANUP_PAYLOAD"


def main() -> None:
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        raise RuntimeError("HF_TOKEN non configurato.")
    api = HfApi(token=token)
    try:
        api.delete_space_secret(repo_id=SPACE_REPO_ID, key=SECRET_NAME)
        print("SPACE_SECRET_REMOVED=True")
    except Exception as exc:
        if "404" not in str(exc):
            raise
        print("SPACE_SECRET_REMOVED=already_absent")
    api.restart_space(repo_id=SPACE_REPO_ID)
    print("SPACE_RESTART_REQUESTED=True")


if __name__ == "__main__":
    main()
