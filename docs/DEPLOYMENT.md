# Deployment guide

Covers every step to deploy SignalForge to Hugging Face Spaces (CPU basic free tier) with Supabase pgvector persistence. All six manual UI steps are included (SPEC.md D12, amended by SPEC-AMENDMENTS.md A7).

## Prerequisites

- GitHub account with SSH or HTTPS access to your fork of this repo
- Hugging Face account
- Supabase account
- A local copy of this repo with the code complete (sentiment, classify, embed, search routers mounted in main.py; all tests green)

---

## Step 1: Create Hugging Face API token

**Why:** SignalForge calls the Hugging Face Inference API for sentiment and zero-shot classification.

**How:**
1. Log in to [huggingface.co](https://huggingface.co)
2. Click your profile icon (top-right) → **Settings**
3. Left sidebar → **Access Tokens**
4. Click **Create new token** (or **New token**)
5. Give it a name (e.g., "SignalForge") and select **Read** permission
6. Click **Create token**
7. Copy the token (starts with `hf_...`)

**Confirm:** You now have a token like `hf_aBcDeFgHiJkLmNoPqRsTuVwXyZ`.

---

## Step 2: Create Supabase project and enable pgvector

**Why:** SignalForge stores embeddings and queries them by cosine similarity.

**Precondition:** Supabase free tier allows only **2 active projects**. Before creating a new one, check your [Supabase dashboard](https://supabase.com/dashboard) under **Projects** and verify you have at least one free-tier slot available. If you have 2 active projects, you must delete one or upgrade to Pro.

**How:**

1. Log in to [supabase.com/dashboard](https://supabase.com/dashboard)
2. Click **New project**
3. Select your organization; enter a project name (e.g., "signalforge")
4. Enter a secure database password (save it in a password manager; you'll need it for migrations)
5. Select the region closest to you
6. Click **Create new project** (wait 1–2 minutes for provisioning)

**Once the project loads:**

7. Left sidebar → **Database** (or **SQL Editor**)
8. Click **Extensions** (or run a query directly)
9. Search for **vector** and click **Enable** (or run: `CREATE EXTENSION IF NOT EXISTS vector;`)

**Apply the migration (one of two methods):**

**Method A: SQL Editor (recommended, no migrations file needed on disk)**
1. In the left sidebar, click **SQL Editor**
2. Click **New query** (or use the **RLS Policy** tab)
3. Paste the following SQL:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  id BIGSERIAL PRIMARY KEY,
  content TEXT NOT NULL,
  embedding VECTOR(384) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_documents_embedding ON documents USING hnsw (embedding vector_cosine_ops);

CREATE OR REPLACE FUNCTION match_documents(
  query_embedding VECTOR(384),
  match_count INT DEFAULT 5
) RETURNS TABLE (id BIGINT, content TEXT, similarity FLOAT8) LANGUAGE SQL STABLE AS $$
  SELECT
    documents.id,
    documents.content,
    1 - (documents.embedding <=> query_embedding) AS similarity
  FROM documents
  ORDER BY documents.embedding <=> query_embedding
  LIMIT match_count;
$$ ;
```

4. Click **Run** (or Cmd+Enter)
5. Confirm the output shows "success" (check the **Results** pane)

**Method B: Direct psql (if you have Postgres CLI installed locally)**
1. In the Supabase dashboard, top-right corner, copy the **Connection string** (Postgres URI)
2. Paste it into your terminal:
   ```bash
   psql "postgres://..." < migrations.sql
   ```
   (if `migrations.sql` exists in the repo; otherwise, copy the SQL from Method A)

**Confirm:** You now have a `documents` table with an `id`, `content`, and `embedding (vector(384))` column.

---

## Step 3: Fill in local .env

**Why:** SignalForge reads HF_API_TOKEN, SUPABASE_URL, and SUPABASE_SERVICE_KEY at runtime.

**How:**

1. In your local copy of the repo, copy `.env.template`:
   ```bash
   cp .env.template .env
   ```

2. Open `.env` and fill in:
   ```
   HF_API_TOKEN=hf_aBcDeFgHiJkLmNoPqRsTuVwXyZ
   SUPABASE_URL=https://abcdefg.supabase.co
   SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ENVIRONMENT=local
   LOG_LEVEL=INFO
   ```

   **Where to find each:**
   - **HF_API_TOKEN:** from Step 1 above
   - **SUPABASE_URL:** Supabase dashboard → **Project Settings** → **API** → **Project URL** (the long `https://...supabase.co` URL)
   - **SUPABASE_SERVICE_KEY:** Supabase dashboard → **Project Settings** → **API** → **Project API Keys** → copy the **service_role** key (not the `anon` key)

3. Save `.env`

**Test locally:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install torch==2.12.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Navigate to `http://localhost:8000/docs` and verify all endpoints load (health, sentiment, classify, embed, search should be visible in the Swagger UI).

---

## Step 4: Create Hugging Face Space and add secrets

**Why:** SignalForge runs in a containerized environment on Hugging Face infrastructure.

**How:**

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click **Create new Space**
3. Choose a name (e.g., `signalforge` or `signalforge-demo`)
4. Select **Owner:** your username
5. Select **Space SDK:** **Docker**
6. Select **Space hardware:** **CPU basic** (free)
7. Click **Create Space**

**Once the Space loads:**

8. Click **Settings** (gear icon, top-right)
9. Left sidebar → **Secrets and variables** (or **Repository secrets**)
10. Click **New secret** and add:
    - Name: `HF_API_TOKEN`, Value: `hf_aBcDeFgHiJkLmNoPqRsTuVwXyZ` (from Step 1)
    - Name: `SUPABASE_URL`, Value: `https://abcdefg.supabase.co` (from Step 3)
    - Name: `SUPABASE_SERVICE_KEY`, Value: `eyJhbGc...` (from Step 3)
    - Name: `ENVIRONMENT`, Value: `production`
    - Name: `LOG_LEVEL`, Value: `INFO`

**Push the code to the Space:**

11. In your local repo, add a Hugging Face remote:
    ```bash
    git remote add hf https://huggingface.co/spaces/<your-username>/<space-name>
    ```
    (Replace `<your-username>` and `<space-name>` with your values)

12. Push the code:
    ```bash
    git push hf main
    ```
    (or `git push hf main -f` if the Space has a conflicting git history)

**Wait for the build and launch:**

The Space will now:
- Clone the repo
- Build the Docker image (reads `Dockerfile`, installs `requirements.txt`)
- Start the app (runs `uvicorn backend.main:app --host 0.0.0.0 --port 7860`)
- Expose it at `https://<your-username>-<space-name>.hf.space`

Build time: 3–5 minutes (includes PyTorch CPU wheels and model downloads on first request).

**Confirm:** Navigate to `https://<your-username>-<space-name>.hf.space/docs` and test the Swagger UI.

---

## Step 5: Update GitHub repo metadata

**Why:** GitHub's About section and search indexing help others discover the project.

**How:**

1. Go to your GitHub repo: `github.com/<username>/signalforge`
2. Click **Settings** (right sidebar, or gear icon)
3. Scroll down to **About** section (or click it on the main repo page)
4. Fill in:
   - **Description:** "Production-grade NLP inference service on Hugging Face models — multi-language sentiment, zero-shot classification, semantic search via pgvector."
   - **Website:** `https://<your-username>-<space-name>.hf.space` (the Space URL from Step 4)
   - **Topics:** `fastapi`, `huggingface`, `nlp`, `sentence-transformers`, `pgvector`, `zero-shot-classification`, `semantic-search`

5. Click **Save** (or press Enter)

---

## Step 6: Demo-day runbook (SPEC-AMENDMENTS.md A7)

**Before any demo, recording, or proposal link-out — run this checklist.**

### (a) Resume Supabase if paused

1. Go to [supabase.com/dashboard](https://supabase.com/dashboard) → your project
2. Click **Settings** (or **Project Status**)
3. If the status shows **Paused**, click **Resume**
4. Wait 30 seconds for resumption

### (b) Wake the Space and allow cold-start

1. Open `https://<your-username>-<space-name>.hf.space/docs` in your browser
2. If the page takes >30 seconds to load, the Space is waking from sleep (~1 minute total)
3. Wait until Swagger UI fully loads and the endpoints are visible

### (c) Run the verification block

Copy and run all five curl commands (replace `BASE=...` with your Space URL):

```bash
BASE=https://<your-username>-<space-name>.hf.space

curl -s $BASE/health | jq .status
# Expected output: "ok"

curl -s -X POST $BASE/api/v1/sentiment \
  -H 'Content-Type: application/json' \
  -d '{"text":"Este producto es increíble, lo recomiendo totalmente"}' \
  | jq '.label, .inference_metadata.provider'
# Expected output: "positive" and either "huggingface_api" or "local"

curl -s -X POST $BASE/api/v1/classify \
  -H 'Content-Type: application/json' \
  -d '{"text":"The party of the first part agrees to indemnify and hold harmless the party of the second part against any and all claims arising from breach of this agreement.","labels":["legal","financial","marketing","technical"]}' \
  | jq .predicted_label
# Expected output: "legal"

curl -s -X POST $BASE/api/v1/embed \
  -H 'Content-Type: application/json' \
  -d '{"documents":["Invoices are due within 30 days","The rocket launched successfully","Quarterly revenue grew 12 percent"]}' \
  | jq '.inference_metadata.model'
# Expected output: "sentence-transformers/all-MiniLM-L6-v2"

curl -s -X POST $BASE/api/v1/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"payment terms","k":2}' \
  | jq '.results[0].document'
# Expected output: "Invoices are due within 30 days" (if previous embed documents are still in Supabase)
```

**All five commands succeed → ready to demo.** If any fails:
- Check that the Space is awake (refresh the `/docs` page)
- Check that Supabase is resumed (no timeouts on embed/search)
- Check that secrets are set correctly in the Space settings
- Check the Space's **Build** log for deployment errors

---

## Monitoring and maintenance

### Keep-alive GitHub Actions workflow

The `.github/workflows/keepalive.yml` workflow runs daily and pings `/health` + `/api/v1/search` to keep both the Space awake and Supabase active.

**To verify it's running:**
1. Go to your GitHub repo → **Actions** tab
2. Look for a workflow named **Keep-alive** or **Keepalive**
3. Check that the latest run shows ✅ (green)

**If the workflow fails:**
- Check the **Build** log for errors (usually indicates the Space URL is wrong or the Space is offline)
- Update the `SPACE_URL` secret in GitHub repo settings if you changed the Space name

### Durability check (SPEC-AMENDMENTS.md A7, Phase 5)

At T+7 days (or after simulating a Supabase pause):
1. Resume Supabase
2. Ping the Space URL
3. Run the five-curl block (Step 6c above)
4. **Pass criteria:** all five succeed, or the runbook restores full function in <5 minutes

This confirms the demo survives a real pause + resume cycle.

---

## Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| Space build fails | Dockerfile syntax, requirements.txt pin conflict, or disk full | Check Space **Build** log; common: `pip install` fails on CPU-only torch (ensure `--index-url https://download.pytorch.org/whl/cpu` is used). |
| `/health` works but `/api/v1/sentiment` hangs | Model downloading on first request (~1 GB) | First inference request may take 2–3 minutes as the sentiment model downloads. Wait, then retry. |
| `/api/v1/embed` or `/api/v1/search` fails with 502/504 | Supabase paused or unreachable | Resume Supabase (Step 6a); check secrets in Space settings. |
| Embed returns empty `embeddings` list | `documents` list was empty or validation failed | Ensure the JSON payload includes `"documents": [...]` with at least one string. |
| Search returns empty `results` | No documents in Supabase yet | Run `/api/v1/embed` with some documents first, then `/api/v1/search`. |
| Sentiment always falls back (`provider: "local"`) | HF API quota exhausted (402 error) | This is expected mid-month; local fallback is working as designed. Contact SheryLabs to reset the demo account's quota, or wait for the monthly reset. |

---

## Next steps after deployment

1. **Record a 60-second demo** walking through the Swagger UI, calling each endpoint, and showing the `inference_metadata` field. Upload to a video platform (YouTube, Loom, etc.) and link from your portfolio.
2. **Update your portfolio/resume** to include the Space URL and a link to the GitHub repo.
3. **Reference SignalForge in Upwork proposals** for Hugging Face, NLP, embeddings, and document classification jobs.
4. **Monitor the keep-alive workflow** (GitHub Actions tab) to ensure the Space and Supabase stay active.

---

## Questions?

- **SPEC.md** for the locked technical contract
- **SPEC-AMENDMENTS.md** for web-verified corrections
- **ARCHITECTURE.md** for design rationale
- **SCALING.md** for free-tier limits and upgrade paths
