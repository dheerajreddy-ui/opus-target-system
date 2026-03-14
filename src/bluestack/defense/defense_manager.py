"""Defense level configuration manager (singleton)."""

import os
from pathlib import Path

import yaml


class DefenseManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._level = int(os.environ.get("DEFENSE_LEVEL", "0"))
        config_path = (
            Path(__file__).parent.parent.parent.parent / "config" / "defense_levels.yaml"
        )
        with open(config_path) as f:
            self._config = yaml.safe_load(f)
        self._current = self._config["levels"][self._level]

    @property
    def level(self) -> int:
        return self._level

    def set_level(self, level: int):
        if level not in self._config["levels"]:
            raise ValueError(f"Invalid defense level: {level}")
        self._level = level
        self._current = self._config["levels"][self._level]

    def is_enabled(self, feature: str) -> bool:
        return bool(self._current.get(feature, False))

    def get_config(self, key: str):
        return self._current.get(key)

    @classmethod
    def reset(cls):
        """Reset singleton (for testing)."""
        cls._instance = None
