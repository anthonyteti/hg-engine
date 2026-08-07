# Research Sources

Snapshot date: 2026-08-07

Primary sources are preferred here so future agents can verify current behavior.

## Pokemon / DS tooling

### HG-Engine

https://github.com/BluRosie/hg-engine

Key facts used:

- HeartGold engine overhaul
- dex/move/ability/item expansion
- Mega Evolution and Primal Reversion
- Fairy type and Hidden Abilities
- build/setup instructions
- project data under the repository
- noncommercial usage expectations

### pret/pokeheartgold

https://github.com/pret/pokeheartgold

Used to understand the state of the HeartGold source/decompilation ecosystem.

### pret/pokeplatinum

https://github.com/pret/pokeplatinum

Used as the fallback/reference DS codebase because of its much more mature source-oriented decompilation.

### Pokemon DS Map Studio

https://github.com/Trifindo/Pokemon-DS-Map-Studio

Key facts used:

- supports Gen 4 and Gen 5 mainline DS games
- tilemap-like map authoring converted to 3D
- source is available for inspection
- current documented user flow is GUI-oriented

### DeSmuME documentation

https://wiki.desmume.org/

Relevant capabilities to investigate:

- command-line frontend
- Lua scripting
- screenshots
- savestates
- ARM9/ARM7 GDB stubs

### melonDS

https://github.com/melonDS-emu/melonDS

Keep as a second emulator/compatibility target and investigate its current automation capabilities during the audit.

## Model and harness sources

### DeepSeek API pricing

https://api-docs.deepseek.com/quick_start/pricing/

Snapshot used:

- V4 Flash: $0.14/M uncached input, $0.28/M output
- V4 Pro: $0.435/M uncached input, $0.87/M output
- 1M context
- warning that significant pricing increases are planned

### DeepSeek agent integrations

https://api-docs.deepseek.com/guides/coding_agents
https://api-docs.deepseek.com/quick_start/agent_integrations/claude_code

Used for:

- Anthropic-compatible DeepSeek endpoint
- Claude Code configuration
- V4 Pro main model / V4 Flash subagent pattern

### OpenAI GPT-5.6

https://openai.com/index/gpt-5-6/

Snapshot used:

- Sol: $5/M input, $30/M output
- Terra: $2.50/M input, $15/M output
- Luna: $1/M input, $6/M output
- Codex availability in supported ChatGPT plans

### Anthropic Sonnet 5

https://www.anthropic.com/news/claude-sonnet-5

Snapshot used:

- introductory API pricing through 2026-08-31: $2/M input, $10/M output
- standard pricing afterward: $3/M input, $15/M output

## Verification rule

Before spending meaningfully on API usage or committing to an external tool API, recheck the official source. Prices, models, repository structure, and project capabilities are time-sensitive.
