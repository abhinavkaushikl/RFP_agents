from __future__ import annotations

import argparse

from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

from rfp_mistral.agent.planner import build_generation_request
from rfp_mistral.retrieval.search import ProposalRetriever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RFP proposal content locally.")
    parser.add_argument("--model-path", required=True, help="Base Mistral model path")
    parser.add_argument("--adapter-path", help="Optional LoRA adapter path")
    parser.add_argument("--index-dir", help="Optional retrieval index directory")
    parser.add_argument("--query", required=True, help="User generation request")
    parser.add_argument("--top-k", type=int, default=3, help="Retrieved examples count")
    parser.add_argument("--max-new-tokens", type=int, default=800)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    tokenizer = AutoTokenizer.from_pretrained(args.model_path, use_fast=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        device_map="auto",
        torch_dtype="auto",
    )

    if args.adapter_path:
        model = PeftModel.from_pretrained(model, args.adapter_path)

    retrieved = []
    if args.index_dir:
        retriever = ProposalRetriever(args.index_dir)
        retrieved = retriever.search(args.query, top_k=args.top_k)

    prompt = build_generation_request(args.query, retrieved)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(
        **inputs,
        max_new_tokens=args.max_new_tokens,
        do_sample=True,
        temperature=0.7,
        top_p=0.9,
        pad_token_id=tokenizer.eos_token_id,
    )

    text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(text)


if __name__ == "__main__":
    main()
