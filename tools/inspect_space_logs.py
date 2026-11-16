from __future__ import annotations

import os
import re

from huggingface_hub import HfApi


SPACE_REPO_ID = "Sibucs/Familiarizzap"
MAX_LINES = 250
INTERESTING = (
    "traceback",
    "error",
    "exception",
    "timeout",
    "timed out",
    "maintenance",
    "commit",
    "delete",
)


def main() -> None:
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        raise RuntimeError("HF_TOKEN non configurato.")
    api = HfApi(token=token)
    matching: list[str] = []
    for raw_line in api.fetch_space_logs(repo_id=SPACE_REPO_ID):
        line = str(raw_line).rstrip()
        if any(marker in line.casefold() for marker in INTERESTING):
            # Participant and event identifiers are fixed-length hexadecimal
            # hashes.  They are not needed for this diagnostic output.
            line = re.sub(r"\b[0-9a-f]{32,64}\b", "[id-redacted]", line)
            matching.append(line)
    print(f"MATCHING_LOG_LINES={len(matching)}")
    for line in matching[-MAX_LINES:]:
        print(line)


if __name__ == "__main__":
    main()
