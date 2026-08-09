---
source_url: "https://arxiv.org/abs/2402.05119"
source_title: "A Closer Look at the Limitations of Instruction Tuning"
source_author: "Sreyan Ghosh, Chandra Kiran Reddy Evuru, Sonal Kumar, Ramaneswaran S, Deepali Aneja, Zeyu Jin, Ramani Duraiswami, Dinesh Manocha"
source_date: "2024-02"
retrieved_date: "2026-08-09"
extracted_concepts: ["LoRA learns style not knowledge", "instruction tuning limitations", "knowledge degradation", "pattern copying"]
tags: ["fine-tuning", "instruction-tuning", "lora", "negative-result", "hallucination", "sft"]
archived_pdf: ""
status: stub
---

**Explains why HORUS's LoRA could not add extraction capability (ADR-067).** Reports that
instruction tuning *"fails to enhance knowledge or skills in LLMs"*; specifically that **LoRA
fine-tuning is limited to learning response initiation and style tokens**, while
full-parameter fine-tuning induces knowledge degradation and increases hallucination by
borrowing tokens from conceptually similar instances in the tuning set. Its headline
conclusion is that *responses generated solely from pre-trained knowledge consistently
outperform responses from models that learn any form of new knowledge from instruction tuning
on open-source datasets.*

Why it matters here: the ADR-067 adapter regressed on all four cells of the 2×2 while the
same base model scored **0.9778** zero-shot on oracle (GT-rendered) text. Schema knowledge was
never the bottleneck — reading was. If LoRA can only move style and response initiation, then
there was no mechanism by which it could close a *reading*-attributable gap, which is exactly
what was observed. Read together with the `spurious_emission` rise, the adapter changed
*how much the model was willing to say* rather than *what it could read*.

Also relevant to ADR-064 ("a prompt-fixable gap is never a fine-tune target"): if IT mainly
transfers style, then any gap closable by better prompting must be closed there first, or the
fine-tune is credited with prompt gains. ADR-066 had already established zero prompt repairs
remained before the LoRA ran, which is what makes the negative result interpretable.

Cite-as-stub per `horus-source-archival`. Author/venue confirmation deferred to the Ch. 8
deep-read.
