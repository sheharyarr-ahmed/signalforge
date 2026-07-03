# Inference metadata on every response

Every response from every inference endpoint carries an `inference_metadata` object (SPEC.md D7):

```json
{
  "model": "cardiffnlp/twitter-xlm-roberta-base-sentiment",
  "provider": "huggingface_api",
  "processing_time_ms": 412,
  "fallback_triggered": false,
  "confidence": 0.97
}
```

- `provider` is exactly `"huggingface_api"` or `"local"` — no other values.
- `model` always carries the full HF repo id (e.g. `sentence-transformers/all-MiniLM-L6-v2`), never a short name.
- `confidence` is `float | null`: the top-label score for sentiment and classify, `null` for embed and search (embeddings have no confidence) — per SPEC-AMENDMENTS.md A10.
- The name is `inference_metadata`, never "citations" (that word belongs to AuditDoc's page-level source attribution — keep the portfolio vocabulary clean).
- Defined once in `backend/schemas/common.py` and composed into every response schema.

**Why:** traceable, verifiable outputs are the discipline this portfolio sells. An endpoint that cannot say which model served it and whether it fell back is not demonstrable.

**How to apply:** no response schema ships without the field; no handler constructs it ad hoc — it is built where the inference happens (service layer), where the timing and provider path are known. Tests assert its presence and correctness on every endpoint, including fallback paths.
