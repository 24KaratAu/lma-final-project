"""generate(): one entry point for every model backend (PLAN.md section 4).

Backends: hf (transformers, 4-bit), vllm, claude_cli, mock. GPU libraries are
imported only when their backend is used, so the mock runs anywhere.
"""

import json
import shutil
import subprocess

from src.common.mocks import mock_generate

_loaded = {}  # (backend, model, adapter) -> loaded model; one model per session in practice


def generate(prompts: list[str], model: str, backend: str = "hf", **kw) -> list[str]:
    """Answer each prompt with `model`.

    kw: max_new_tokens (512), temperature (0 = greedy), seed (0), batch_size (hf, 4),
        adapter (path to a LoRA adapter; hf and vllm), system (claude_cli system prompt),
        vllm_kw (extra vllm.LLM arguments, e.g. {"tensor_parallel_size": 2} for a 7B model on two T4s).
    """
    if backend == "mock":
        return mock_generate(prompts, model)
    if backend == "hf":
        return _hf(prompts, model, **kw)
    if backend == "vllm":
        return _vllm(prompts, model, **kw)
    if backend == "claude_cli":
        return _claude_cli(prompts, model, **kw)
    raise ValueError(f"unknown backend {backend!r}")


def _hf(prompts, model, max_new_tokens=512, temperature=0.0, seed=0, batch_size=4, adapter=None, **_):
    import torch
    from transformers import set_seed

    set_seed(seed)
    tok, net = _load_hf(model, adapter)
    out = []
    for i in range(0, len(prompts), batch_size):
        chats = [_chat(tok, p) for p in prompts[i : i + batch_size]]
        enc = tok(chats, return_tensors="pt", padding=True, add_special_tokens=False).to(net.device)
        sample = {"do_sample": True, "temperature": temperature} if temperature > 0 else {"do_sample": False}
        with torch.no_grad():
            ids = net.generate(**enc, max_new_tokens=max_new_tokens, pad_token_id=tok.pad_token_id, **sample)
        out += tok.batch_decode(ids[:, enc["input_ids"].shape[1] :], skip_special_tokens=True)
    return out


def _load_hf(model, adapter=None):
    key = ("hf", model, adapter)
    if key not in _loaded:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        tok = AutoTokenizer.from_pretrained(model, padding_side="left")
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        quant = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,  # T4 and P100 have no bf16
            bnb_4bit_use_double_quant=True,
        )
        net = AutoModelForCausalLM.from_pretrained(model, quantization_config=quant, device_map="auto")
        if adapter:
            from peft import PeftModel

            net = PeftModel.from_pretrained(net, adapter)
        _loaded[key] = (tok, net.eval())
    return _loaded[key]


def _chat(tok, prompt):
    return tok.apply_chat_template([{"role": "user", "content": prompt}], tokenize=False, add_generation_prompt=True)


def _vllm(prompts, model, max_new_tokens=512, temperature=0.0, seed=0, adapter=None, vllm_kw=None, **_):
    from vllm import LLM, SamplingParams

    key = ("vllm", model, adapter)
    if key not in _loaded:
        llm_kw = {"dtype": "half", "seed": seed, "enable_lora": bool(adapter), "max_model_len": 4096} | (vllm_kw or {})
        _loaded[key] = LLM(model=model, **llm_kw)
    llm = _loaded[key]
    lora = None
    if adapter:
        from vllm.lora.request import LoRARequest

        lora = LoRARequest("adapter", 1, adapter)
    tok = llm.get_tokenizer()
    params = SamplingParams(temperature=temperature, max_tokens=max_new_tokens, seed=seed)
    outs = llm.generate([_chat(tok, p) for p in prompts], params, lora_request=lora)
    return [o.outputs[0].text for o in outs]


def _claude_cli(prompts, model, system=None, **_):
    """Claude Code print mode with tools off (PLAN.md section 9): one call per prompt, prompt on stdin."""
    exe = shutil.which("claude") or "claude"
    cmd = [exe, "-p", "--tools", "", "--model", model, "--output-format", "json"]
    if system:
        cmd += ["--system-prompt", system]
    out = []
    for p in prompts:
        res = subprocess.run(cmd, input=p, capture_output=True, text=True, encoding="utf-8", check=True)
        out.append(json.loads(res.stdout)["result"])
    return out
