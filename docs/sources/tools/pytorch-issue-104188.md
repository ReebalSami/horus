---
source_url: "https://github.com/pytorch/pytorch/issues/104188"
source_title: "MPS: Add `torch.mps.max_memory_allocated()` for tracking peak GPU memory usage"
source_author: "PyTorch contributors (issue thread)"
source_date: "2023-06-26"
retrieved_date: "2026-05-20"
extracted_concepts: []
tags: ["pytorch", "mps", "apple-silicon", "memory-tracking", "issue-thread", "horus-adr-017"]
archived_pdf: ""
status: stub
---

PyTorch issue #104188 — request for `torch.mps.max_memory_allocated()` to mirror the CUDA API for tracking peak GPU memory usage on the MPS backend. Open since 2023-06-26 (no PR landed as of 2026-05-20). The issue thread documents the **community workaround** adopted by HORUS in ADR-017 §"Decision 2 (D2.A)": pre/post snapshots of `torch.mps.driver_allocated_memory()` around the operation under test, reporting the post value as a steady-state proxy for peak. This workaround **misses transient peaks during generation** — disclosed limitation in ADR-017. Cited in HORUS as the authoritative source for "why we don't have a one-line peak-memory call on MPS"; the supersession trigger for ADR-017 is this issue closing with a landed PR. For MLX-routed extractors, MLX's `mx.get_peak_memory()` provides the true-peak API and the limitation does not apply.
