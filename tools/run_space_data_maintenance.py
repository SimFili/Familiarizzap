from __future__ import annotations

import json
import os
import sys
import time

from gradio_client import Client
from huggingface_hub import HfApi


SPACE_REPO_ID = "Sibucs/Familiarizzap"
SPACE_URL = "https://sibucs-familiarizzap.hf.space"
SECRET_NAME = "DATA_CLEANUP_PAYLOAD"


def main() -> int:
    token = os.environ.get("HF_TOKEN", "")
    raw_payload = os.environ.get("DATA_CLEANUP_PAYLOAD", "")
    if not token or not raw_payload:
        raise RuntimeError("Credenziali di manutenzione non configurate.")
    payload = json.loads(raw_payload)
    request_key = str(payload.get("request_key", ""))
    if not request_key:
        raise RuntimeError("request_key mancante.")

    api = HfApi(token=token)
    api.add_space_secret(
        repo_id=SPACE_REPO_ID,
        key=SECRET_NAME,
        value=raw_payload,
    )
    try:
        api.restart_space(repo_id=SPACE_REPO_ID)
        last_error: Exception | None = None
        for attempt in range(60):
            try:
                client = Client(SPACE_URL, verbose=False)
                raw_result = client.predict(
                    request_key,
                    api_name="/maintenance_cleanup",
                )
                result = json.loads(str(raw_result))
                print("MAINTENANCE_RESULT=" + json.dumps(result, sort_keys=True))
                return 0 if result.get("ok") else 2
            except Exception as exc:
                last_error = exc
                if attempt and attempt % 6 == 0:
                    print("SPACE_STATUS=waiting", flush=True)
                time.sleep(10)
        raise RuntimeError(
            f"Endpoint di manutenzione non disponibile: {type(last_error).__name__}"
        )
    finally:
        api.delete_space_secret(repo_id=SPACE_REPO_ID, key=SECRET_NAME)
        api.restart_space(repo_id=SPACE_REPO_ID)
        print("SPACE_SECRET_REMOVED=True")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
