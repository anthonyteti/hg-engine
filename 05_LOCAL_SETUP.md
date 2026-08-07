# Local Setup: Windows + WSL

## Recommended environment

Use **WSL2 with Ubuntu** as the primary development environment.

Reasons:

- HG-Engine documents WSL/Linux dependencies directly.
- Codex, Claude Code, Git, Python, compilers, and shell tooling work naturally there.
- Agents can run builds and scripts without driving Windows GUI applications.
- It keeps the project close to a normal Linux CI environment.

Docker remains useful as a clean-build verification path, but do not make Docker the only development route initially because reverse-engineering and debugging tools may need direct filesystem/process access.

## 1. Install WSL if needed

From an elevated PowerShell session:

```powershell
wsl --install -d Ubuntu
```

Restart if Windows requests it, then open Ubuntu and complete first-run user creation.

## 2. Install base tooling in WSL

Use the dependency list from the current HG-Engine README as source of truth. At the research snapshot it included packages equivalent to:

```bash
sudo apt update
sudo apt install -y \
  git \
  build-essential \
  cmake \
  python3 \
  python3-pip \
  python3-venv \
  libpng-dev \
  automake \
  autoconf \
  gcc-arm-none-eabi \
  pkg-config
```

If the current upstream README differs, follow upstream and record the change in `docs/AUTOMATION_AUDIT.md`.

## 3. Clone or fork HG-Engine

Preferred long-term approach: create your own GitHub fork of HG-Engine, then clone the fork.

Generic local form:

```bash
mkdir -p ~/git
cd ~/git
git clone --recursive <YOUR_HG_ENGINE_FORK_URL> autonomous-pokemon-ds
cd autonomous-pokemon-ds
```

Add upstream:

```bash
git remote add upstream https://github.com/BluRosie/hg-engine.git
git fetch upstream
```

If no fork exists yet, clone upstream temporarily, but do not begin substantial project work without establishing a project-owned Git remote.

## 4. Copy this planning pack into the repository

Place the Markdown files from this pack at the repository root.

The resulting root should include at least:

```text
00_README.md
01_PROJECT_SPEC.md
02_RESEARCH_AND_DECISIONS.md
03_ARCHITECTURE.md
04_ROADMAP.md
05_LOCAL_SETUP.md
AGENTS.md
MODEL_STRATEGY.md
INITIAL_AGENT_PROMPT.md
GEN5_FUTURE.md
SOURCES.md
```

## 5. Base ROM handling

HG-Engine expects the user to provide a compatible English Pokemon HeartGold ROM locally.

Do not put the ROM in Git.

Before placing it in the project, confirm `.gitignore` excludes at minimum:

```gitignore
*.nds
*.sav
*.dsv
*.state
*.dst
rom.nds
test.nds
```

Also ignore generated asset/cache directories once their locations are known.

Follow the current HG-Engine README for the expected local ROM filename and revision.

## 6. Prove the unmodified build

Before using an LLM to change anything:

```bash
make -j"$(nproc)"
```

Expected result according to the current HG-Engine documentation is a generated `test.nds`.

Record:

- successful command
- compiler/tool versions
- build duration if useful
- output filename
- any warnings

If the baseline does not build, fix the environment before giving an agent a feature task.

## 7. Optional Docker baseline

HG-Engine also documents a Docker build flow. Use it as a reproducibility check after the normal WSL build works.

The exact commands can change, so prefer the repository's current README. At the research snapshot the flow included building an HG-Engine image and invoking its ROM-maker script.

## 8. Coding harness option A: DeepSeek through Claude Code

This is the recommended cost-first experiment.

Install Node.js 18+ and Claude Code using the current official Anthropic installation method. DeepSeek's current integration documentation uses:

```bash
npm install -g @anthropic-ai/claude-code
```

Then set the DeepSeek environment variables for the shell session. Do **not** save your API key inside the repository.

Current documented pattern:

```bash
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN='<YOUR_DEEPSEEK_API_KEY>'
export ANTHROPIC_MODEL='deepseek-v4-pro[1m]'
export ANTHROPIC_DEFAULT_OPUS_MODEL='deepseek-v4-pro[1m]'
export ANTHROPIC_DEFAULT_SONNET_MODEL='deepseek-v4-pro[1m]'
export ANTHROPIC_DEFAULT_HAIKU_MODEL='deepseek-v4-flash'
export CLAUDE_CODE_SUBAGENT_MODEL='deepseek-v4-flash'
export CLAUDE_CODE_EFFORT_LEVEL=max
```

Launch from the project root:

```bash
claude
```

Paste the contents of `INITIAL_AGENT_PROMPT.md` or instruct the agent to read and execute it.

Because model names/integration behavior are time-sensitive, verify these environment variables against DeepSeek's current official Claude Code integration page before first use.

## 9. Coding harness option B: Codex

Keep Codex installed as the escalation harness.

Use it when:

- the DeepSeek agent gets stuck on a build/reverse-engineering problem
- you want an independent architecture review
- you need stronger multimodal/screenshot reasoning
- a large change deserves a second implementation opinion

Start Codex from the repository root so it automatically sees `AGENTS.md` and the project documentation.

Do not ask both harnesses to independently reread the entire repository every day. Preserve findings under `docs/knowledge/` and have later sessions consume those notes.

## 10. First session

The first coding session must execute only the Stage 0 audit.

Prompt:

```text
Read INITIAL_AGENT_PROMPT.md and execute it. Do not begin game-content production.
```

Expected main deliverable:

```text
docs/AUTOMATION_AUDIT.md
```

Do not approve full game development until that audit gives HeartGold a credible headless map path.

## 11. After the audit

Run a second-model review of `docs/AUTOMATION_AUDIT.md`.

Ask the reviewer to challenge:

- unsupported assumptions
- GUI dependencies disguised as automation
- binary formats that are not actually understood
- fragile ROM patching
- missing reproducibility steps
- whether Platinum would now be cheaper overall

Only then approve Stage 1 and Stage 2.
