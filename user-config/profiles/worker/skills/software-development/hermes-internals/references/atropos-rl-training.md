# Atropos RL Training Integration

How Hermes Agent integrates with [Atropos](https://github.com/NousResearch/atropos) (Nous Research's LLM RL Gym) for reinforcement learning training.

## Architecture: Two-Component Split

```
Hermes Agent (环境执行器)
    ↓ rollout / trajectory
Atropos API Server (run-api)  ← 居中收集、存储、评分
    ↓ batch pull
Trainer (GRPO / PPO / Axolotl / Tinker)
    ↓ updated weights
Inference Server (vLLM / SGLang)
    ↓ next-round inference
Hermes Agent (next round) → loop
```

Hermes is the **environment executor** — it runs tool-calling, multi-turn conversations and produces scored trajectories. Atropos is the **orchestration framework** — it collects trajectories, scores them, and feeds them to the trainer.

## Hermes-Side Key Source Paths

### `hermes rl` command

`hermes_cli/main.py:11162`:
```python
_AGENT_COMMANDS = {None, "chat", "acp", "rl"}
```

`rl` is a first-class agent command alongside `chat` and `acp`. It goes through the same startup path (`_prepare_agent_startup`, MCP discovery, plugin loading). The `_should_background_mcp_startup` function at line 11187 includes `"rl"` in the check, so MCP servers start in background for RL sessions.

### Trajectory generation

| File | Role |
|------|------|
| `agent/trajectory.py` | Core trajectory saver — ShareGPT-compatible JSONL (`from: human/gpt/system/tool`) |
| `batch_runner.py` | Multi-process parallel agent runner — reads dataset JSONL, runs agent per prompt, collects trajectories with `tool_stats` and `tool_error_counts` |
| `run_agent.py` | `_save_trajectory()` — called at end of each conversation when `agent.save_trajectories: true` |

Output files:
- `trajectory_samples.jsonl` — completed conversations
- `failed_trajectories.jsonl` — failed/interrupted conversations

### Trajectory format (ShareGPT-compatible)

Each line is a JSON object with:
- `conversations`: array of `{from: "human"|"gpt"|"system"|"tool", value: "..."}`
- `timestamp`, `model`, `completed`
- Batch runner adds: `prompt_index`, `metadata`, `tool_stats` (per-tool count/success/failure), `tool_error_counts`, `api_calls`

Normalization:
- Reasoning → `<think>` tags (from native thinking tokens or REASONING_SCRATCHPAD XML)
- Tool calls → `<tool_call>{"name": "...", "arguments": {...}}</tool_call>`
- Tool responses → `<tool_response>{"tool_call_id": "...", "name": "...", "content": ...}</tool_response>`
- Empty `<think>` blocks inserted for turns without reasoning — ensures consistent training data format

### RL toolset status

The `rl` toolset was previously listed in `_DEFAULT_OFF_TOOLSETS` but has been **removed** from the current code:

`hermes_cli/tools_config.py:115`:
```python
_DEFAULT_OFF_TOOLSETS = {"moa", "homeassistant", "spotify", "discord",
                          "discord_admin", "video", "video_gen", "x_search"}
```

`cron/scheduler.py:96` still has a stale comment referencing `{moa, homeassistant, rl}` but the code no longer includes `rl` in the exclusion set.

RL mode is now activated via the `hermes rl` CLI command, not via toolset toggling.

## Atropos Key Components

GitHub: https://github.com/NousResearch/atropos (1.3k stars, MIT)

| Directory | Purpose |
|-----------|---------|
| `atroposlib/` | Core library — `BaseEnv`, `ManagedServer`, API server |
| `environments/` | Ready-to-use RL environments (GSM8K, tool calling, RLAIF, code execution, multimodal) |
| `example_trainer/` | Reference trainer (GRPO-based) |

### Environment types

- **Dataset environments**: GSM8K, MMLU — static data evaluation
- **Online environments**: Blackjack, Taxi — interactive game-based learning
- **RLAIF / RLHF**: LLM Judge/Reward Models — preference alignment
- **Multi-turn RL**: tool calling, deepresearch — complex multi-step interactions
- **Code execution**: MBPP, HumanEval — generate + execute code
- **Multimodal**: OCR VQA, Clevr — vision + language

### Training algorithm: GRPO

Atropos's example trainer uses **Group Relative Policy Optimization**:
- No separate value model (critic) needed — more memory-efficient than PPO
- Generates group of responses per prompt, scores them, uses group average as baseline
- Reinforces responses above the group mean
- Same algorithm family as DeepSeek-R1

### Trainer integrations

| Integration | Characteristics |
|-------------|----------------|
| Axolotl + Atropos Plugin | Mature LoRA/QLoRA fine-tuning, YAML config, DeepSpeed |
| Tinker-Atropos | Lightweight LoRA trainer, CPU control loop + GPU backend |
| Example Trainer (GRPO) | Atropos's own reference implementation |

## Data Flow: Hermes ↔ Atropos

1. Start Atropos API server: `run-api` (default `localhost:8000`)
2. Start Hermes environment: `hermes rl` or `batch_runner.py` — produces scored trajectory data
3. Trajectories sent to Atropos API via HTTP (`/scored_data` or `/scored_data_list`)
4. Trainer pulls batches via `GET /batch`
5. Trainer updates model weights (GRPO, PPO, etc.)
6. Updated model deployed to inference server (vLLM/SGLang)
7. Cycle repeats

Atropos also supports **On-Policy Distillation (OPD)**: teacher model generates token-level distillation data (`distill_token_ids` + `distill_logprobs`), student model learns teacher's token distribution alongside RL rewards. Teacher and student must share tokenizer vocabulary.

## Reported Results

From the Atropos README:

- **Tool Calling**: BFCL Parallel Tasks 10%→46% (4.6x), Simple Tasks 21%→51.75% (2.5x)
- **Financial Prediction**: Directional accuracy 20%→50% (2.5x)

Model artifacts on HuggingFace:
- `NousResearch/DeepHermes-ToolCalling-Specialist-Atropos`
- `NousResearch/DeepHermes-Financial-Fundamentals-Prediction-Specialist-Atropos`
- `NousResearch/DeepHermes-Egregore-v1-RLAIF-8b-Atropos`

## Debugging / Development Tools

Atropos provides:
- `view-run` — Gradio UI to inspect rollout batches
- `process` subcommand — inference-only rollouts, outputs JSONL + HTML visualization
- `evaluate` subcommand — runs environment's evaluate method
- `atropos-sft-gen` / `atropos-dpo-gen` — convert rollouts to SFT/DPO training data
- WandB integration — experiment tracking via `use_wandb=True`

## Strategic Analysis: Why Hermes Ships RL Code\n\nThe RL training code exists in Hermes not because it's a user-facing feature, but because **Hermes is the execution layer of Nous's training pipeline**. This is analogous to a factory's production line — users drive the cars, not the welding robots.\n\n### The self-bootstrapping cycle\n\n```\nAtropos trains model\n    ↑ needs real environment for rollout generation\nHermes provides this environment (tool-calling, multi-turn, real execution)\n    ↑ needs to get better at agent tasks\nAtropos trains better model → deploys to Hermes → better rollouts → better training → repeat\n```\n\nHermes and Atropos are two gears in one self-improving loop. Neither works without the other.\n\n### Strategic positioning vs Anthropic/OpenAI\n\n| | Anthropic/OpenAI | Nous Research |\n|---|---|---|\n| Model | Closed-source | Open-source (HuggingFace) |\n| Training method | Undisclosed | Atropos + GRPO, fully open |\n| Environment | Undisclosed | Hermes Agent, fully open |\n| User training | Cannot | Can (Atropos + Hermes + own GPU) |\n| Revenue model | API billing | Managed inference (Portal) + enterprise |\n\nNous is not competing on the same axis (selling model access). They're building **open training infrastructure** so organizations can own and fine-tune their own models — a fundamentally different bet than the MaaS (Model-as-a-Service) approach.\n\n### Privacy: trajectory saving is opt-in and local-only\n\nKey code evidence that Hermes **does not** send user conversations to Atropos or Nous:\n\n- `run_agent.py:1704`: `if not self.save_trajectories: return` — default `False`, no-op unless explicitly enabled\n- `agent/agent_init.py:169`: `save_trajectories: bool = False` — parameter default\n- `agent/trajectory.py:52`: `open(filename, \"a\")` — pure local file write, zero network calls\n- `batch_runner.py:331`: `save_trajectories=False` — even batch mode explicitly disables internal saving\n- Search for `upload.*trajector|post.*trajector|telemetry` in `agent/` — **zero matches**\n\nTraining data comes from Nous's internal runs of `batch_runner.py` against public datasets (GSM8K, MMLU, HumanEval, etc.), not from user conversations.\n\n### Who actually uses this\n\n- **99% of users**: Never touch RL. They benefit indirectly — the models they run were trained using this pipeline.\n- **Advanced users with custom tool environments**: Can run `batch_runner.py` with their own datasets and tool configs, produce custom trajectories, and train domain-specific models.\n\n### Comparison with DeepSeek's approach\n\nBoth Nous and DeepSeek use GRPO-based online RL, but their environments differ because their training targets differ:\n\n- **DeepSeek**: Lightweight rule-based reward (math/programming answer verification via regex or test execution). R1's breakthrough came from applying GRPO at scale to tasks with naturally clean reward signals.\n- **Nous**: Heavy environment layer (real tool execution, multi-turn agent rollouts) because tool-calling capability can't be verified by pattern matching — it requires actual execution.\n\nBoth approaches are valid; they optimize for different capabilities. DeepSeek's insight was that simple reward signals at massive scale can produce emergent reasoning. Nous's insight is that real environment feedback is necessary for practical agent capabilities.\n\n## Hermes Docs Coverage

- `website/docs/getting-started/learning-path.md:103` — mentions Atropos in "I want to train models" path
- `website/docs/developer-guide/trajectory-format.md` — full trajectory format specification
- `website/docs/user-guide/features/tools.md:13` — mentions "RL training" in tool categories
- No dedicated RL training page exists on the Hermes docs site (404 on `/docs/developer-guide/rl-training` and `/docs/developer-guide/rl-pipeline`)
