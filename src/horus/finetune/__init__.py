"""Structurer fine-tuning (issue #55, re-aimed per ADR-034 supersession trigger #2).

Text-only LoRA fine-tuning of the Arm-B structurer (`google/gemma-4-E4B-it`) on
the orchestrated pipeline's text→JSON step. The reader (Granite) is NOT the
bottleneck (reads ~0.98; Arm B already extracts ~0.95) — the structurer is the
shippable lever, so it is the fine-tune target.

Modules:
  - ``dataset`` — corpus discovery (full ZUGFeRD set via the embedded factur-x
    GT route, beyond the 26 wired XML-Rechnung pairs), GT→target-JSON
    serialization with a scorer self-consistency check, and (question, answer)
    training-pair construction in the mlx-vlm LoRA dataset shape.

Refs: ADR-034 (arms + structurer choice + no-HARKing), ADR-038 (arms mechanism),
ADR-035/041/042 (schema + repeating-group scoring), ADR-007 (mlx-vlm).
"""

from __future__ import annotations
