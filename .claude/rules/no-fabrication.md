# No fabrication

Every claim in README, docs, commit messages, and proposals must be true of the code as shipped (SPEC.md D14).

**Allowed claims:** production NLP pipeline on HF open-source models · multi-language sentiment with API/local fallback · zero-shot classification with custom label sets · local embeddings via sentence-transformers · vector search on Supabase pgvector · cost-optimization patterns.

**Forbidden claims:** custom model training · fine-tuning · custom embeddings · GPU-optimized inference · production traffic at scale · any technology not actually used in this repo.

**Why:** the repo backs Upwork bids; a single inflated claim poisons the whole portfolio.

**How to apply:** before writing any outward-facing text (README, SCALING.md, About description), diff each claim against the allowed list. Docs must disclose free-tier limitations honestly — under-claiming is acceptable, over-claiming never is.
