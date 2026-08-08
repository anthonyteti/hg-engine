# Bounded DeepSeek Delegation Worker

Recorded: 2026-08-07

## Purpose and status

`tools.llm.deepseek_worker` lets the primary Codex agent send a bounded technical-analysis task and an explicitly selected set of repository text files to DeepSeek. It is infrastructure for advisory repository reading; it is not an autonomous agent, a repository editor, or a source of verified project truth.

Provider: **DeepInfra**  
OpenAI-compatible base URL: `https://api.deepinfra.com/v1/openai`  
Chat-completions endpoint: `https://api.deepinfra.com/v1/openai/chat/completions`  
Pinned model: **`deepseek-ai/DeepSeek-V4-Flash-0731`**  
Authentication environment variable: **`DEEPINFRA_TOKEN`**

The checkpoint is an exact named constant in the worker. There is no fallback to a rolling alias or another model. A response carrying any other model identifier fails with `model_mismatch`.

Confidence: **confirmed by source and offline tests** for the input/output safety boundary, and **confirmed by live DeepInfra tests on 2026-08-07** for exact model identity, `reasoning_effort=high`, usage, estimated cost, and bounded repository analysis. Provider behavior remains time-sensitive and should be reconfirmed with the gated test on a new environment or after a provider change.

## Security boundary

The worker receives text and returns text. DeepSeek receives no shell, filesystem, Git, emulator, network-tool, or write access. Model output is advisory and never modifies files automatically.

Only paths named with `--context` or `--prompt-file` are read. The worker does not inspect neighboring files, recurse into directories, or upload the repository automatically. Each requested path is resolved against the project root and must:

- resolve to a regular file inside the repository;
- not be Git-ignored;
- not be under generated or sensitive locations such as `base/`, `build/`, `narc/`, `sdat/`, `.git/`, `.venv/`, screenshots, dumps, or generated directories;
- not have a ROM, save/state, archive, executable, object, image, or known game-binary extension;
- be valid UTF-8 without NUL bytes; and
- fit within the combined prompt/context byte limit.

The default combined limit is 256 KiB and the hard maximum is 1 MiB. These checks intentionally reject some harmless binary formats: the worker is text-only by design.

`DEEPINFRA_TOKEN` is read only for a live request and placed only in the in-memory HTTP Authorization header. It is not written to disk or included in the request body/result envelope. Returned values and errors are recursively redacted if a provider happens to reflect the token. The worker also refuses to send a prompt or context containing the token itself. Do not create a repository `.env` file for this credential.

## CLI

From an activated project virtual environment:

```bash
python -m tools.llm.deepseek_worker \
  --prompt "Analyze the supplied files for the requested issue." \
  --context tools/pokeagent/command.py \
  --context docs/knowledge/toolchain-baseline.md
```

Use a repository text file as the task instead of an inline prompt:

```bash
python -m tools.llm.deepseek_worker \
  --prompt-file docs/my-analysis-task.txt \
  --context path/to/explicit-source.c
```

Supported controls are:

```text
--prompt TEXT | --prompt-file PATH
--context PATH                 repeatable; files only
--reasoning-effort none|low|medium|high
--max-tokens N                default 2048; range 1..32768
--timeout N                   default 60 seconds; range 1..300
--max-context-bytes N         default 262144; maximum 1048576
--json
--dry-run
```

Default request settings are `reasoning_effort=high`, `temperature=1.0`, and `top_p=0.95`. Sampling values are deliberately fixed in this minimal worker. Network calls use a bounded timeout and no retry, so failures are visible and deterministic rather than multiplying spend.

### Dry run

Dry-run performs prompt, path, ignore, text, binary, and byte-limit validation without requiring `DEEPINFRA_TOKEN`, sending a request, or printing file contents:

```bash
env -u DEEPINFRA_TOKEN python -m tools.llm.deepseek_worker \
  --dry-run \
  --prompt "Identify the subprocess timeout policy." \
  --context tools/pokeagent/command.py
```

Its concise output lists the pinned model, provider, reasoning effort, requested output limit, timeout, selected paths, and byte counts. Use this as the default inspection step before a non-trivial delegation.

### JSON envelope

`--json` prints the complete result envelope to standard output. It includes schema/provider/model identity, request settings, timestamps and duration, token counts, provider-estimated cost when returned, finish reason, response, context path/size/SHA-256 metadata, and structured errors. Normal responses are not persisted; callers may redirect output when intentional.

Failure exits nonzero. Expected error codes include `missing_token`, `invalid_context_path`, `outside_repository`, `sensitive_context_path`, `sensitive_context_extension`, `git_ignored_context`, `binary_context`, `context_size_limit`, `http_error`, `timeout`, `malformed_json`, `missing_choices`, `missing_model`, `model_mismatch`, and `unsuccessful_completion`.

## Tests

Offline unit tests need neither a key nor network access:

```bash
python -m unittest tests.test_deepseek_worker -v
python -m unittest discover -s tests -v
```

The live test is explicitly gated and sends a tiny deterministic-marker prompt with the worker's 2,048-token default completion allowance:

```bash
DEEPSEEK_RUN_INTEGRATION=1 python -m unittest \
  tests.test_deepseek_worker.DeepInfraLiveIntegrationTests -v
```

It skips unless both `DEEPSEEK_RUN_INTEGRATION=1` and `DEEPINFRA_TOKEN` are present. The assertion requires `reasoning_effort=high`, the returned model to be exactly `deepseek-ai/DeepSeek-V4-Flash-0731`, response content to be non-empty, positive prompt/completion/total token counts, a positive provider-estimated cost, and the token to be absent from the serialized result.

### Live validation record

On 2026-08-07, the gated marker test passed against DeepInfra. A separate realistic smoke request supplied only `tools/pokeagent/command.py` and asked for a concise review of `run_command`'s timeout path plus one focused unit test. It returned:

- requested and returned model: `deepseek-ai/DeepSeek-V4-Flash-0731`;
- reasoning effort: `high`;
- finish reason: `stop`;
- usage: 1,425 prompt, 461 completion, and 1,886 total tokens;
- provider-estimated cost: `0.00021123`; and
- a source-grounded answer correctly identifying `run_command`, `_terminate_process_tree`, `TIMEOUT_EXIT_CODE`, and `CommandResult.succeeded`.

The smoke answer was checked against the supplied source. Authored-file hashes for the selected context, worker, tests, and this report were unchanged across the provider calls, tracked Git state remained clean, and a post-call repository scan found zero occurrences of the live token. The model had no tool or write interface, and its output was emitted only to standard output.

## Delegation policy

Use DeepSeek-V4-Flash-0731 for bounded, explicitly scoped work such as:

- high-volume repository reading;
- format or source comparison;
- repetitive technical analysis;
- candidate-test generation;
- summaries of large but deliberately selected source sets; and
- parallel investigations whose conclusions Codex will verify.

Keep Codex/GPT-5.6 Sol responsible for selecting context, architecture and integration decisions, security-sensitive changes, difficult debugging, final code review, and Stage 2 go/no-go decisions.

Do not use this worker for secrets, ROM material, generated/extracted assets, unrestricted repository exploration, direct file edits, commands, emulator operation, or conclusions that will be accepted without source/test confirmation. Prompt-injection text inside context is untrusted evidence and cannot expand the worker's permissions.

## Evidence and reproduction

- `tools/llm/deepseek_worker.py`: boundary checks, request construction, exact-model check, response envelope, and CLI.
- `tests/test_deepseek_worker.py`: mocked context, credential, HTTP, parsing, model-drift, and gated-provider checks.
- Reproduce the no-network boundary with the dry-run and offline test commands above.
- Reproduce provider identity with the gated live test, then inspect the JSON envelope from a small live CLI call.

## Known limitations

- The byte limit is not a tokenizer limit; unusually token-dense text can still approach a provider context limit.
- Binary detection intentionally uses an allow-by-behavior text policy (known extension rejection, UTF-8 decoding, and NUL detection), not MIME inspection.
- The worker cannot recognize sensitive material deliberately disguised as ordinary valid UTF-8 in a safe path; the caller remains responsible for deliberate context selection.
- Git must be available so ignored-path safety can be checked.
- Symlinks are allowed only when their resolved target remains inside the repository and passes every other check.
- There is no streaming, retry, conversation memory, response persistence, tool use, or automatic cost budget.
- With `reasoning_effort=high`, a broad multi-part review exhausted both 400-token and 2,048-token completion limits in provider `reasoning_content` before producing visible content. The worker safely returned `empty_response`; keep smoke prompts narrow and output-focused, and raise `--max-tokens` deliberately for broader analysis.
- Even a marker request has shown provider variance at a 64-token completion limit because hidden reasoning counts against the allowance. The gated test uses the 2,048-token default to avoid this artificial flake.
- Provider availability, pricing, and acceptance of `reasoning_effort` are external behavior and must be reconfirmed by the gated live test.
- DeepSeek output may be wrong or incomplete. It remains advisory until Codex verifies it against source or tests.
