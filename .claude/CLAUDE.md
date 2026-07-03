# SignalForge — Project Bible

Production-grade NLP inference service on Hugging Face open-source models. FastAPI, CPU-only, $0 budget. Portfolio artifact for SheryLabs. The full contract lives in `SPEC.md` — read it before any non-trivial change; its Decisions (D1–D14) are locked and override convenience. `SPEC-AMENDMENTS.md` records web-verified corrections (dead API host, 402 error class, model sizes, HNSW, Spaces contract) — where it amends a decision, the amendment wins.

## Rules

The files in `.claude/rules/` are auto-loaded and always apply: no-fabrication, error-handling (four-class HF taxonomy), bounded-retry, inference-metadata, no-claude-attribution.

## Operating principles

- **Think before coding.** State assumptions. If a locked decision (D1–D14) seems wrong, stop and say so — do not silently deviate.
- **Simplicity first.** Minimum code that satisfies SPEC.md. Anything in "Out of scope" stays out, even if trivial to add.
- **Surgical changes.** Touch only what the task requires. Match existing style.
- **Goal-driven.** "Works" means the phase gate in SPEC.md §Verification passes. `verify.sh` (pytest) must be green before a turn ends.

## Anti-pattern checklist (reject on sight)

- Generic `try/except Exception` around HF calls — error handling is four-class (402 quota / 429 rate-limit / 5xx transient / timeout), each routed differently.
- Retry loops without the hardcoded cap (max 2 attempts total, 250 ms delay, transient class only).
- Any reference to `api-inference.huggingface.co` — that host is dead; the router is `router.huggingface.co/hf-inference/models/{id}`.
- Validation logic in route handlers — field constraints live in Pydantic schemas.
- `Any` types, implicit coercion, non-strict Pydantic models.
- Responses missing `inference_metadata`.
- `print()` or stdlib `logging` — structlog JSON only.
- Adding auth, rate limiting, caching layers, CI/CD, or a frontend — all explicitly out of scope in v1.
- Config read from `os.environ` directly — Pydantic Settings in `backend/config.py` is the only env boundary.

## Workflow

- Conventional commits, one commit per completed unit: `feat(sentiment):`, `test(retry):`, `docs(scaling):`. Imperative mood.
- Git author: Sheharyar Ahmed <sheharyar.softwareengineer@gmail.com> (repo-local config, already set).
- Manual UI steps (HF token, Supabase setup, Space creation — SPEC.md D12): STOP, print exact instructions, wait for confirmation. Never assume they happened.
- Models are locked (D5): sentiment `cardiffnlp/twitter-xlm-roberta-base-sentiment`, zero-shot `facebook/bart-large-mnli`, embeddings `sentence-transformers/all-MiniLM-L6-v2` (384-dim). No substitutions without a spec change.
