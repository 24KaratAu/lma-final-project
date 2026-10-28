"""QLoRA fine-tuning of the verifier on kept training pairs (4-bit base, fp16 for T4 and P100).

python -m src.train.qlora --model Qwen/Qwen2.5-7B-Instruct --data runs/gen-full/kept.jsonl \
    --out /kaggle/working/runs/qlora-250 --limit 250

Checkpoints every --save-steps and at least every 30 minutes; rerunning the
same command resumes from the last checkpoint (Kaggle's 12-hour cutoff).
Writes train_log.json with steps, time and peak GPU memory.
"""

import argparse
import json
import math
import random
import time
from pathlib import Path

from src.train.gen_pairs import to_example


def tokenize(tok, prompt: str, target: str, max_len: int) -> dict:
    """Chat-formatted prompt + target; loss only on the target tokens. Long prompts are cut from the left."""
    chat = tok.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True)
    p_ids = tok(chat, add_special_tokens=False)["input_ids"]
    t_ids = tok(target + tok.eos_token, add_special_tokens=False)["input_ids"]
    room = max_len - len(t_ids)
    p_ids = p_ids[-room:] if room > 0 else []
    return {"input_ids": (p_ids + t_ids)[:max_len], "labels": ([-100] * len(p_ids) + t_ids)[:max_len]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True, help="kept.jsonl from src.train.gen_pairs")
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=None, help="train on the first N pairs (learning curve)")
    ap.add_argument("--max-len", type=int, default=1024)
    ap.add_argument("--max-steps", type=int, default=-1)
    ap.add_argument("--epochs", type=float, default=2)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--grad-accum", type=int, default=8)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--save-steps", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, Trainer, TrainerCallback, TrainingArguments, set_seed,
    )
    from transformers.trainer_utils import get_last_checkpoint

    set_seed(args.seed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pairs = [json.loads(line) for line in open(args.data, encoding="utf-8") if line.strip()]
    random.Random(args.seed).shuffle(pairs)
    pairs = pairs[: args.limit] if args.limit else pairs

    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    data = [tokenize(tok, *to_example(p), args.max_len) for p in pairs]

    quant = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16, bnb_4bit_use_double_quant=True,
    )
    net = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=quant, device_map="auto")
    net = prepare_model_for_kbit_training(net, use_gradient_checkpointing=True)
    net = get_peft_model(
        net, LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05, target_modules="all-linear", task_type="CAUSAL_LM")
    )

    def collate(batch):
        width = max(len(b["input_ids"]) for b in batch)
        pad = lambda seq, v: seq + [v] * (width - len(seq))  # noqa: E731
        return {
            "input_ids": torch.tensor([pad(b["input_ids"], tok.pad_token_id) for b in batch]),
            "labels": torch.tensor([pad(b["labels"], -100) for b in batch]),
            "attention_mask": torch.tensor([pad([1] * len(b["input_ids"]), 0) for b in batch]),
        }

    class SaveEvery30Min(TrainerCallback):
        last = time.time()

        def on_step_end(self, targs, state, control, **kw):
            if time.time() - self.last > 1800:
                control.should_save, self.last = True, time.time()

    # 3% warmup, in steps: transformers 5 dropped warmup_ratio
    total = args.max_steps if args.max_steps > 0 else math.ceil(len(data) * args.epochs / args.grad_accum)
    targs = TrainingArguments(
        output_dir=str(out), per_device_train_batch_size=1, gradient_accumulation_steps=args.grad_accum,
        num_train_epochs=args.epochs, max_steps=args.max_steps, learning_rate=args.lr, lr_scheduler_type="cosine",
        warmup_steps=max(1, int(0.03 * total)), fp16=True, logging_steps=5, save_steps=args.save_steps, save_total_limit=2,
        gradient_checkpointing=True, report_to=[], seed=args.seed,
    )
    trainer = Trainer(model=net, args=targs, train_dataset=data, data_collator=collate, callbacks=[SaveEvery30Min()])

    gpus = range(torch.cuda.device_count())  # device_map="auto" can spread the model over both T4s
    for i in gpus:
        torch.cuda.reset_peak_memory_stats(i)
    start = time.time()
    trainer.train(resume_from_checkpoint=get_last_checkpoint(str(out)))
    trainer.save_model(str(out / "adapter"))

    log = {
        "args": vars(args),
        "pairs": len(data),
        "longest_input_tokens": max(len(d["input_ids"]) for d in data),
        "steps": trainer.state.global_step,
        "minutes": round((time.time() - start) / 60, 2),
        "peak_gpu_gb": round(sum(torch.cuda.max_memory_allocated(i) for i in gpus) / 2**30, 2),
        "peak_gpu_gb_per_gpu": [round(torch.cuda.max_memory_allocated(i) / 2**30, 2) for i in gpus],
        "gpu": torch.cuda.get_device_name(0),
        "final_loss": next((h["loss"] for h in reversed(trainer.state.log_history) if "loss" in h), None),
    }
    (out / "train_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(json.dumps(log, indent=2))


if __name__ == "__main__":
    main()
