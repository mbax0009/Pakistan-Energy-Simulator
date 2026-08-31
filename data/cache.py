from __future__ import annotations

import hashlib
import json
import os
import shutil

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class CacheEntry:
    namespace: str
    key: str
    path: Path
    created_at: datetime
    payload: dict[str, Any]


class JsonResourceCache:
    """Small deterministic JSON cache for provider responses.

    The default location is relative to the running application, which keeps
    development and standalone data beside the D:-hosted project instead of
    silently consuming the system drive. Set ``PAK_ENERGY_CACHE_DIR`` to move
    it explicitly.
    """

    def __init__(self, root: str | Path | None = None):
        configured = os.environ.get("PAK_ENERGY_CACHE_DIR")
        selected = Path(root) if root is not None else Path(
            configured or Path.cwd() / "cache" / "resources"
        )
        self.root = selected.resolve()

    @staticmethod
    def build_key(material: Mapping[str, Any]) -> str:
        canonical = json.dumps(
            material,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_namespace(namespace: str) -> str:
        normalized = namespace.strip().lower().replace("_", "-")
        if not normalized or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789-"
            for character in normalized
        ):
            raise ValueError("Cache namespace contains unsupported characters.")
        return normalized

    def _path(self, namespace: str, key: str) -> Path:
        namespace = self._validate_namespace(namespace)
        if len(key) != 64 or any(character not in "0123456789abcdef" for character in key):
            raise ValueError("Cache key must be a lowercase SHA-256 digest.")
        return self.root / namespace / f"{key}.json"

    def get(
        self,
        namespace: str,
        material: Mapping[str, Any],
        *,
        max_age_seconds: float | None = None,
    ) -> CacheEntry | None:
        key = self.build_key(material)
        path = self._path(namespace, key)
        if not path.is_file():
            return None

        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            created_at = datetime.fromisoformat(envelope["created_at"])
            payload = envelope["payload"]
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if max_age_seconds is not None:
            age = (datetime.now(timezone.utc) - created_at).total_seconds()
            if age > max_age_seconds:
                return None

        if not isinstance(payload, dict):
            return None

        return CacheEntry(
            namespace=self._validate_namespace(namespace),
            key=key,
            path=path,
            created_at=created_at,
            payload=payload,
        )

    def put(
        self,
        namespace: str,
        material: Mapping[str, Any],
        payload: Mapping[str, Any],
    ) -> CacheEntry:
        key = self.build_key(material)
        path = self._path(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        created_at = datetime.now(timezone.utc)
        normalized_payload = dict(payload)
        envelope = {
            "created_at": created_at.isoformat(),
            "payload": normalized_payload,
        }
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(envelope, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, path)
        return CacheEntry(
            namespace=self._validate_namespace(namespace),
            key=key,
            path=path,
            created_at=created_at,
            payload=normalized_payload,
        )

    def clear(self, namespace: str | None = None) -> int:
        """Clear this cache root or one validated namespace.

        Returns the number of cached JSON entries removed. Targets are always
        resolved below the exact cache root.
        """

        target = self.root
        if namespace is not None:
            target = self.root / self._validate_namespace(namespace)
        target = target.resolve()
        if target != self.root and self.root not in target.parents:
            raise ValueError("Cache clear target escaped the configured cache root.")
        if not target.exists():
            return 0
        count = sum(1 for path in target.rglob("*.json") if path.is_file())
        shutil.rmtree(target)
        return count

    def entry_count(self) -> int:
        if not self.root.exists():
            return 0
        return sum(1 for path in self.root.rglob("*.json") if path.is_file())

