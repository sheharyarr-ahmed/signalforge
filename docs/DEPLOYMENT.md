# Deployment guide

> Populated in Phase 4. Covers every step, including the six manual steps (SPEC.md D12 as amended by SPEC-AMENDMENTS.md A7):

1. Hugging Face account + API token (Settings → Access Tokens)
2. Supabase project + enabling the `vector` extension (Dashboard → Database → Extensions). Precondition: verify a free-plan project slot is available (Supabase free allows only 2 active projects) before creating.
3. Local `.env` from `.env.template`
4. Creating the HF Space (Docker SDK, CPU basic free) + Space secrets
5. GitHub repo metadata (About, topics, website → live Space URL)
6. Demo-day runbook (SPEC-AMENDMENTS.md A7): before any demo, recording, or proposal link-out — (a) resume the Supabase project if paused, (b) ping the Space URL and allow ~1 min cold wake, (c) run the five-curl block from SPEC.md §Verification.
