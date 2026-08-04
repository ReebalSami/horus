---
source_url: "https://github.com/anthropics/anthropic-sdk-python"
source_title: "Anthropic SDK for Python — Messages API (vision input, output_config.effort, structured outputs, models.list)"
source_author: "Anthropic"
source_date: ""
retrieved_date: "2026-08-04"
extracted_concepts: []
tags: ["anthropic", "claude", "messages-api", "vision", "structured-outputs", "llm-judge", "ground-truth", "horus-adr-060"]
archived_pdf: ""
status: stub
---

Anthropic Python SDK — the capabilities HORUS ADR-060 relies on for authoring held-out
ground truth with a cloud vision judge. Retrieved 2026-08-04 via the `context7` MCP
(`/anthropics/anthropic-sdk-python`), per `context7-and-docs-first`; not from
training-data recall.

**Verified capabilities** (each quoted from current SDK sources, not paraphrased from memory):

**1. Vision input — base64 image content blocks, multiple per request.** From
`examples/images.py` and `src/anthropic/types/base64_image_source_param.py`:

```python
class Base64ImageSourceParam(TypedDict, total=False):
    data: Required[Annotated[Union[str, Base64FileInput], PropertyInfo(format="base64")]]
    media_type: Required[Literal["image/jpeg", "image/png", "image/gif", "image/webp"]]
    type: Required[Literal["base64"]]
```

`data` accepts `str` **or** `Base64FileInput`, so a `pathlib.Path` may be passed and the
SDK performs the base64 encoding. Relevance to HORUS: the 58 held-out page rasters are
already PNG at 300 DPI, and a multi-page invoice can be sent as several image blocks in
one message so the judge sees the whole document at once.

**2. `output_config.effort` — the effort lever.** From
`src/anthropic/types/output_config_param.py`:

```python
class OutputConfigParam(TypedDict, total=False):
    effort: Optional[Literal["low", "medium", "high", "xhigh", "max"]]
    """All possible effort levels."""
    format: Optional[JSONOutputFormatParam]
```

Context7 note: *"effort lives on output_config, budget_tokens lives on thinking — they
are different TypedDicts with zero cross-validation code in the entire repo. Both can be
sent together because they are independent optional request fields."* Relevance: ADR-060
specifies `effort="xhigh"` for GT authoring; this confirms the level exists and is
independent of the thinking budget.

**3. `output_config.format` — schema-locked structured outputs.** Relevance: the judge's
reply can be constrained to the GT schema, so an answer key never depends on the
`validate_and_repair` path (ADR-035) that free-form local-model JSON requires.

**4. `thinking` — three modes.** From `src/anthropic/types/thinking_config_param.py`:

```python
ThinkingConfigParam: TypeAlias = Union[
    ThinkingConfigEnabledParam, ThinkingConfigDisabledParam, ThinkingConfigAdaptiveParam
]
```

`enabled` carries an explicit `budget_tokens` (minimum 1,024, counted against
`max_tokens`); `adaptive` has no `budget_tokens` field at all; `disabled` turns it off.

**5. `client.models.list()` — runtime model discovery.** From
`src/anthropic/resources/models.py`: *"List available models. The Models API response
can be used to determine which models are available for use in the API. **More recently
released models are listed first.**"* `retrieve()` additionally resolves an alias to a
concrete model ID and returns `ModelInfo` with `max_input_tokens` / `max_tokens`.
Relevance: HORUS resolves the strongest available model from the caller's own account
rather than pinning an ID this session cannot verify still exists. SDK examples currently
show `model="claude-sonnet-5"`; `claude-opus-4-6` appears in
`MODELS_TO_WARN_WITH_THINKING_ENABLED`.

**Auth**: `Anthropic()` reads `ANTHROPIC_API_KEY` from the environment. HORUS keeps it in
a git-ignored `.env` (`.gitignore:42`, confirmed with `git check-ignore -v .env`) and
never commits it.
