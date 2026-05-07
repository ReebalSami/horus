"""Reproducibility seeding primitive (python-ml-uv brainstorm B8=C).

Sets all relevant random sources for deterministic ML runs. Stdlib seeds are
always applied; `numpy` and `torch` are seeded only if importable so this
module works in environments without optional ML deps installed (e.g., during
`/start-project --dry-run` validation).

Example:
    from your_pkg.seeding import set_global_seed

    set_global_seed(42)
    # ... train / evaluate ...
"""

from __future__ import annotations

import os
import random
from typing import Final

DEFAULT_SEED: Final[int] = 42


def set_global_seed(seed: int = DEFAULT_SEED) -> None:
    """Seed all reachable random sources for reproducibility.

    Always seeds:
        - `os.environ['PYTHONHASHSEED']` (must be set before any hash-using imports
          to fully take effect; export it via your shell for the strongest guarantee)
        - stdlib `random`

    Conditionally seeds (only if installed):
        - `numpy.random` (legacy global RNG; consumer should also seed
          `numpy.random.default_rng(seed)` if using the new Generator API)
        - `torch` (CPU + CUDA all-devices + cudnn deterministic mode)

    Never raises on missing optional deps.
    """
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)

    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass

    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    except ImportError:
        pass
