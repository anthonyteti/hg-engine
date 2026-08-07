# Model and Harness Strategy

Pricing snapshot: 2026-08-07. Prices and model availability change quickly. Recheck official pricing before large runs.

## Recommendation

Use a **tiered model strategy**, not one frontier model for every token.

### Tier A: high-volume cheap agent work

Primary candidate: DeepSeek V4.

Current official DeepSeek API prices per 1M tokens:

| Model | Input cache miss | Output | Context |
|---|---:|---:|---:|
| DeepSeek V4 Flash | $0.14 | $0.28 | 1M |
| DeepSeek V4 Pro | $0.435 | $0.87 | 1M |

Cache-hit input is currently much cheaper still.

DeepSeek explicitly supports agent integrations and an Anthropic-compatible API. Its official docs show Claude Code configured with V4 Pro as the main model and V4 Flash for subagents. DeepSeek also documents V4 Flash as adapted to agent/code workflows.

Important: DeepSeek has publicly warned that it expects to raise API pricing significantly. Treat the above as a current opportunity, not a permanent budget assumption.

### Tier B: strong engineering escalation

Use GPT-5.6 Terra or another strong coding model for tasks where the cheap worker is failing repeatedly, such as:

- difficult C/ARM interaction bugs
- linker or overlay problems
- reverse engineering of poorly understood game behavior
- complex cross-repository refactors
- architecture review before committing to a format

Current OpenAI API list price for GPT-5.6 Terra is $2.50/M input and $15/M output. Luna is $1/M input and $6/M output. Sol is $5/M input and $30/M output.

If a ChatGPT plan already provides useful Codex allowance, use that allowance before unnecessarily routing all engineering through paid API tokens.

### Tier C: frontier second opinion

Use a top model only when the expected cost of a wrong solution is higher than the model cost.

Examples:

- deciding whether to abandon HeartGold for Platinum
- validating a dangerous binary-format assumption before large-scale generation
- auditing a Mega/Pokedex expansion that affects save compatibility
- diagnosing a failure after multiple cheaper agents disagree

Claude Sonnet 5 is currently $2/M input and $10/M output through 2026-08-31, then scheduled to move to $3/M and $15/M. Opus-family models are more expensive.

## Recommended harness setup

### Cheapest serious option

Use **Claude Code pointed at DeepSeek's Anthropic-compatible API**:

- main agent: `deepseek-v4-pro[1m]`
- subagents: `deepseek-v4-flash`
- high/max reasoning only for hard tasks

DeepSeek's official integration documentation provides this exact pattern.

This gives a mature coding-agent shell while billing DeepSeek API rates rather than Anthropic model rates.

### Alternative

Use an open model-agnostic harness such as OpenCode, or a DeepSeek-oriented CLI, if you want to avoid coupling the workflow to Claude Code.

### Frontier escalation

Keep Codex available as a second harness for difficult work.

The repository files in this pack are intentionally harness-neutral. `AGENTS.md` should work in Codex, Claude Code, and most agentic terminal tools.

## Routing policy

Use the cheapest model likely to complete the task correctly.

Suggested routing:

| Task | Default |
|---|---|
| search repository for formats/usages | V4 Flash |
| summarize source areas | V4 Flash |
| generate YAML/data/tests | V4 Flash |
| write straightforward Python tooling | V4 Flash or V4 Pro |
| implement nontrivial parser/compiler | V4 Pro |
| multi-file refactor with build loop | V4 Pro |
| reverse engineer ARM/binary behavior | V4 Pro, escalate if stuck |
| architecture review | GPT-5.6 Terra/Sol or Sonnet 5 |
| persistent hard build failure | frontier escalation |
| bulk Pokemon data conversion | V4 Flash + deterministic validator |
| visual judgment | use a multimodal model only when screenshots matter |

## Token-control rules

1. Keep `AGENTS.md` concise enough to remain in every session.
2. Store discoveries in small focused notes, not one enormous research file.
3. Ask agents to search before reading whole directories.
4. Generate machine-readable inventories once and reuse them.
5. Use subagents for independent bounded investigations, not redundant full-project reads.
6. Compact/summarize old session context into repository docs.
7. Separate design discussions from implementation loops when possible.
8. Never use a frontier model to mass-generate deterministic table data that a cheaper model plus validator can handle.

## Illustrative token cost

For a large batch totaling 50M uncached input tokens and 5M output tokens, using current list rates:

- DeepSeek V4 Flash: about $8.40
- DeepSeek V4 Pro: about $26.10
- GPT-5.6 Luna: about $80
- Claude Sonnet 5 at current introductory price: about $150
- GPT-5.6 Terra: about $200
- GPT-5.6 Sol: about $400

These are simple list-price examples, not forecasts. Caching, subscription allowances, reasoning overhead, retries, tool output, and future pricing can materially change actual spend.

## Practical starting choice

Start the audit with DeepSeek V4 Pro as the main coding agent and V4 Flash for subagents if you are comfortable using API billing.

After the audit, run one independent frontier review of `docs/AUTOMATION_AUDIT.md` before committing to the HeartGold map compiler architecture.

That gives cheap breadth plus expensive judgment only at the decision point where it matters.
