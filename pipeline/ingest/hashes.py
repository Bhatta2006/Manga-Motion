"""One shared byte-hash contract for ingest and downstream stages."""

import hashlib
import json

from pipeline.cache import page_sha256


def object_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode("utf-8")).hexdigest()


__all__ = ["page_sha256", "object_hash"]
