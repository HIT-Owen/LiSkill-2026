"""LoRA supervised fine-tuning of Qwen3.5-9B (§3.3.3).

Reproduction settings from §4.1.4:

    base model      Qwen3.5-9B
    LoRA            r = 8, alpha = 16, all attention/MLP projections
    optimiser       AdamW, lr = 1e-4
    batch size      8 (gradient accumulation), 5 epochs, early stop on dev loss
    loss            negative log-likelihood of the output part only (eq. (5))

The module is import-safe without the training stack; the heavy imports happen
inside :func:`train` so that `import liskill` never requires torch.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class LoRAConfig:
    base_model: str = "Qwen/Qwen3.5-9B"
    output_dir: str = "out/qwen3.5-9b-liskill-lora"
    train_file: str = "out/understanding/train.jsonl"
    dev_file: str = "out/understanding/dev.jsonl"
    r: int = 8
    alpha: int = 16
    dropout: float = 0.05
    learning_rate: float = 1e-4
    epochs: int = 5
    batch_size: int = 1
    grad_accum: int = 8
    max_length: int = 1024
    warmup_ratio: float = 0.03
    logging_steps: int = 20
    save_steps: int = 200


def build_prompt_completion_dataset(path: str | Path):
    """Load a JSONL split as a prompt/completion dataset."""
    from datasets import load_dataset

    return load_dataset("json", data_files=str(path), split="train")


def train(config: Optional[LoRAConfig] = None) -> str:
    """Fine-tune the adapter and return the output directory."""
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainingArguments,
    )

    config = config or LoRAConfig()
    tokenizer = AutoTokenizer.from_pretrained(config.base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model = get_peft_model(
        model,
        LoraConfig(
            r=config.r,
            lora_alpha=config.alpha,
            lora_dropout=config.dropout,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        ),
    )

    def tokenize(example):
        prompt_ids = tokenizer(example["prompt"], add_special_tokens=False)["input_ids"]
        target_ids = tokenizer(example["completion"] + tokenizer.eos_token, add_special_tokens=False)[
            "input_ids"
        ][: config.max_length]
        input_ids = (prompt_ids + target_ids)[: config.max_length]
        # eq. (5): the prompt tokens do not contribute to the loss
        labels = [-100] * min(len(prompt_ids), config.max_length) + target_ids
        labels = labels[: len(input_ids)]
        return {"input_ids": input_ids, "labels": labels, "attention_mask": [1] * len(input_ids)}

    dataset = load_dataset(
        "json", data_files={"train": config.train_file, "dev": config.dev_file}
    )
    tokenized = dataset.map(tokenize, remove_columns=dataset["train"].column_names)

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=config.output_dir,
            per_device_train_batch_size=config.batch_size,
            gradient_accumulation_steps=config.grad_accum,
            learning_rate=config.learning_rate,
            num_train_epochs=config.epochs,
            warmup_ratio=config.warmup_ratio,
            logging_steps=config.logging_steps,
            save_steps=config.save_steps,
            evaluation_strategy="steps",
            eval_steps=config.save_steps,
            load_best_model_at_end=True,
            bf16=True,
            optim="adamw_torch",
            report_to=[],
        ),
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["dev"],
        data_collator=DataCollatorForSeq2Seq(tokenizer, padding=True),
    )
    trainer.train()
    trainer.save_model(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)
    return config.output_dir


if __name__ == "__main__":  # pragma: no cover - requires the training stack
    print(train())
