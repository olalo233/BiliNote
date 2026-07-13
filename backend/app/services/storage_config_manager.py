"""Runtime configuration for object-storage sources and feature bindings."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)

SECRET_MASK = "••••"

DEFAULT_CONFIG: dict[str, Any] = {
    "sources": {},
    "image_bed": {
        "enabled": False,
        "source": "",
        "public_base_url": "",
        "path_prefix": "",
    },
    "assets": {
        "enabled": False,
        "source": "",
    },
}


class StorageConfigManager:
    """Read and write storage.json on every operation without caching."""

    def __init__(self, filepath: str = "config/storage.json"):
        self.path = Path(filepath)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _empty_config(self) -> dict[str, Any]:
        return {
            "sources": {},
            "image_bed": dict(DEFAULT_CONFIG["image_bed"]),
            "assets": dict(DEFAULT_CONFIG["assets"]),
        }

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty_config()
        try:
            with self.path.open("r", encoding="utf-8") as file:
                raw = json.load(file)
        except Exception as exc:
            logger.warning("读取对象存储配置失败 (%s): %s", self.path, exc)
            return self._empty_config()

        if not isinstance(raw, dict):
            logger.warning("对象存储配置不是 JSON object (%s)", self.path)
            return self._empty_config()

        config = self._empty_config()
        if isinstance(raw.get("sources"), dict):
            config["sources"] = raw["sources"]
        for feature in ("image_bed", "assets"):
            if isinstance(raw.get(feature), dict):
                config[feature].update(raw[feature])
        return config

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
        temp_path.replace(self.path)

    def get_config(self) -> dict[str, Any]:
        """Return the current raw configuration, including secrets internally."""

        return self._read()

    def get_source(self, name: str) -> dict[str, Any] | None:
        source = self._read().get("sources", {}).get(name)
        return dict(source) if isinstance(source, dict) else None

    def list_sources(self) -> dict[str, dict[str, Any]]:
        return {
            name: dict(source)
            for name, source in self._read().get("sources", {}).items()
            if isinstance(source, dict)
        }

    def upsert_source(self, name: str, source: dict[str, Any]) -> dict[str, Any]:
        config = self._read()
        existing = config["sources"].get(name, {})
        updated = dict(source)
        secret = updated.get("secret_key")
        if not secret or is_secret_masked(str(secret)):
            updated["secret_key"] = existing.get("secret_key", "")
        config["sources"][name] = updated
        self._write(config)
        return dict(updated)

    def delete_source(self, name: str) -> bool:
        config = self._read()
        if name not in config["sources"]:
            return False
        del config["sources"][name]
        self._write(config)
        return True

    def update_feature(self, feature: str, values: dict[str, Any]) -> dict[str, Any]:
        if feature not in ("image_bed", "assets"):
            raise ValueError(f"不支持的存储功能: {feature}")
        config = self._read()
        config[feature].update(values)
        self._write(config)
        return dict(config[feature])

    def is_feature_enabled(self, feature: str) -> bool:
        config = self._read()
        feature_config = config.get(feature, {})
        source_name = feature_config.get("source")
        enabled = bool(feature_config.get("enabled"))
        if enabled and source_name not in config.get("sources", {}):
            logger.warning(
                "对象存储功能 %s 引用了不存在的 source=%s，按未启用处理",
                feature,
                source_name,
            )
            return False
        return enabled and bool(source_name)

    def get_effective_feature(self, feature: str) -> dict[str, Any]:
        config = self._read()
        values = dict(config.get(feature, {}))
        values["enabled"] = self.is_feature_enabled(feature)
        return values

    def get_public_config(self) -> dict[str, Any]:
        config = self._read()
        public_sources = {}
        for name, source in config.get("sources", {}).items():
            if not isinstance(source, dict):
                continue
            sanitized = dict(source)
            sanitized["secret_key"] = mask_secret(sanitized.get("secret_key", ""))
            public_sources[name] = sanitized

        return {
            "sources": public_sources,
            "image_bed": self.get_effective_feature("image_bed"),
            "assets": self.get_effective_feature("assets"),
        }


def is_secret_masked(value: str) -> bool:
    return value == SECRET_MASK or value.startswith(SECRET_MASK)


def mask_secret(secret: str | None) -> str:
    if not secret:
        return ""
    secret = str(secret)
    return f"{SECRET_MASK}{secret[-4:]}"


storage_config_manager = StorageConfigManager()
