"""Configuration scaffold (python-ml-uv brainstorm B8=C stdlib-only primitives).

Defers the config-layer choice (Hydra / pydantic / argparse / typer / etc.) to
per-project decision at consumption time. Ships a stdlib `@dataclass`
placeholder; consumer extends or replaces with their preferred tooling.

Example (default):
    from horus.config import Config

    cfg = Config(seed=42, learning_rate=1e-3)
    print(cfg)

Swap pattern (Hydra):
    @hydra.main(version_base=None, config_path="conf", config_name="config")
    def main(cfg: DictConfig) -> None:
        ...

Swap pattern (pydantic):
    from pydantic import BaseModel

    class Config(BaseModel):
        seed: int = 42
        learning_rate: float = 1e-3
        # ...

Swap pattern (typer + dataclass):
    @app.command()
    def train(seed: int = 42, learning_rate: float = 1e-3, ...) -> None:
        cfg = Config(seed=seed, learning_rate=learning_rate)
        ...
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    """Minimal experiment configuration. Extend as your project grows."""

    seed: int = 42
    learning_rate: float = 1e-3
    batch_size: int = 32
    num_epochs: int = 1
