# HF Spaces Docker SDK contract (SPEC-AMENDMENTS.md A6): the container runs as
# UID 1000 non-root, disk is ephemeral (models must be baked in at build time),
# and the app serves on port 7860. Host-agnostic otherwise.
FROM python:3.11-slim

RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    HF_HOME=/home/user/.cache/huggingface \
    PATH=/home/user/.local/bin:$PATH

WORKDIR /app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user torch==2.12.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir --user -r requirements.txt

# Bake both local models into the image — runtime disk is wiped on every
# restart, and a post-sleep wake must never re-download ~1.1 GB of weights.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" \
    && python -c "from transformers import AutoModelForSequenceClassification, AutoTokenizer; m='cardiffnlp/twitter-xlm-roberta-base-sentiment'; AutoModelForSequenceClassification.from_pretrained(m); AutoTokenizer.from_pretrained(m)"

COPY --chown=user . .

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
