# RFP Mistral

Local pipeline for building an RFP and proposal generation system on top of a self-hosted Mistral model.

## What This Project Does

- Normalizes raw RFP and proposal documents into a structured dataset
- Builds instruction-tuning examples for Mistral
- Creates a lightweight retrieval index over historical proposals
- Fine-tunes a Mistral base model with LoRA
- Runs local generation with retrieval-augmented context for better proposal quality

## Why Mistral Instead Of Training From Scratch

Training a competitive language model from scratch requires a very large corpus, significant GPU budget, and weeks of training. For an RFP system, the practical path is:

1. Start from a strong open-weight Mistral base model
2. Fine-tune it on your RFP and proposal data
3. Add retrieval so the model can ground answers in prior winning proposals

This repo is built for that approach.

## Project Layout

```text
.
├── configs/
│   ├── dataset.example.yaml
│   └── train.example.yaml
├── data/
│   ├── processed/
│   ├── raw/
│   └── samples/
├── src/rfp_mistral/
│   ├── agent/
│   ├── data/
│   ├── inference/
│   ├── retrieval/
│   ├── training/
│   └── schemas.py
└── tests/
```

## Expected Dataset Format

Place your normalized records in `data/raw/rfp_records.jsonl`.

Each line should look like:

```json
{
  "id": "rfp-001",
  "client_name": "Acme Health",
  "industry": "Healthcare",
  "rfp_title": "Cloud Modernization and Managed Services",
  "rfp_summary": "The client is seeking a partner to migrate workloads to cloud.",
  "requirements": [
    "Migrate 120 virtual machines",
    "Provide 24x7 managed support",
    "Meet HIPAA compliance requirements"
  ],
  "evaluation_criteria": [
    "Technical capability",
    "Past performance",
    "Pricing"
  ],
  "solution_summary": "Phased migration with managed SOC and cloud operations.",
  "proposal_sections": {
    "executive_summary": "We propose a phased transformation program...",
    "technical_approach": "We will assess, migrate, validate, and optimize...",
    "implementation_plan": "The work will be delivered in four waves...",
    "pricing_notes": "Commercials depend on final workload discovery."
  },
  "tags": ["cloud", "migration", "managed-services", "healthcare"]
}
```

## Quick Start

### 1. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 2. Prepare training examples

```bash
python -m rfp_mistral.data.prepare_dataset \
  --input data/raw/rfp_records.jsonl \
  --output data/processed/train.jsonl
```

### 3. Build retrieval index

```bash
python -m rfp_mistral.retrieval.build_index \
  --input data/raw/rfp_records.jsonl \
  --output-dir data/index
```

### 4. Fine-tune Mistral with LoRA

```bash
python -m rfp_mistral.training.train_lora \
  --config configs/train.example.yaml
```

### 5. Generate an answer or draft section

```bash
python -m rfp_mistral.inference.generate \
  --model-path mistralai/Mistral-7B-Instruct-v0.2 \
  --adapter-path checkpoints/rfp-mistral-lora \
  --index-dir data/index \
  --query "Draft an executive summary for a healthcare cloud migration RFP"
```

### 6. Run The Workflow In Jupyter

Open [rfp_mistral_workflow.ipynb](/Users/abhinavkaushik/Documents/RFP_LLM/notebooks/rfp_mistral_workflow.ipynb) if you want the same pipeline in notebook form.

## Recommended System Design

- Base model: Mistral 7B Instruct or a Mistral-compatible open-weight derivative
- Fine-tuning: LoRA or QLoRA
- Retrieval: sentence-transformer embeddings + FAISS
- Agent pattern:
  - Retrieve similar proposals
  - Build a scoped prompt with requirements and constraints
  - Generate one section at a time
  - Run a post-check for compliance coverage and missing requirements

## Suggested Next Step

Start by converting 50 to 200 historical RFP and proposal pairs into the JSONL format above. Once that data exists, this repo can produce the first fine-tuned checkpoint.
