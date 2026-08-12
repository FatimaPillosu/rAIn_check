"""Load config.toml (plan §9: "model path and context length from config.toml")."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.toml"
REPO_ROOT = CONFIG_PATH.parent


@dataclass
class ModelConfig:
    key: str
    label: str
    path: Path
    licence: str
    chat_format: str

    def available(self) -> bool:
        return self.path.exists()


@dataclass
class AssistantConfig:
    active_model: str
    context_length: int
    max_tokens_per_reply: int
    n_threads: int
    models: dict[str, ModelConfig]


def load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def load_assistant_config(path: Path = CONFIG_PATH) -> AssistantConfig:
    raw = load_config(path)
    a = raw["assistant"]
    models = {}
    for key, m in a.get("models", {}).items():
        models[key] = ModelConfig(
            key=key, label=m["label"], path=REPO_ROOT / m["path"],
            licence=m["licence"], chat_format=m["chat_format"],
        )
    return AssistantConfig(
        active_model=a.get("active_model", "none"),
        context_length=a.get("context_length", 2048),
        max_tokens_per_reply=a.get("max_tokens_per_reply", 300),
        n_threads=a.get("n_threads", 4),
        models=models,
    )
