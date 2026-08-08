from __future__ import annotations

import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
import urllib.error

from tools.llm import deepseek_worker as worker


class FakeResponse:
    def __init__(self, payload: object, *, status: int = 200) -> None:
        self.status = status
        self.body = (
            payload
            if isinstance(payload, bytes)
            else json.dumps(payload).encode("utf-8")
        )

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]


def completion_response(
    *,
    model: str = worker.MODEL_ID,
    content: str = "analysis",
    finish_reason: str = "stop",
    estimated_cost: float | None = 0.000012,
) -> dict[str, object]:
    usage: dict[str, object] = {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }
    if estimated_cost is not None:
        usage["estimated_cost"] = estimated_cost
    return {
        "model": model,
        "choices": [
            {
                "finish_reason": finish_reason,
                "message": {"role": "assistant", "content": content},
            }
        ],
        "usage": usage,
    }


class RepositoryFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(
            ["git", "init", "--quiet"],
            cwd=self.root,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_bytes(self, relative_path: str, data: bytes) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def write_text(self, relative_path: str, text: str) -> Path:
        return self.write_bytes(relative_path, text.encode("utf-8"))

    def prepared(self, *, prompt: str = "Inspect the supplied evidence.") -> worker.PreparedInput:
        return worker.prepare_input(
            project_root=self.root,
            prompt=prompt,
            prompt_file=None,
            context_paths=[],
        )


class ConfigurationTests(RepositoryFixture):
    def test_exact_pinned_defaults_and_endpoint(self) -> None:
        self.assertEqual(worker.MODEL_ID, "deepseek-ai/DeepSeek-V4-Flash-0731")
        self.assertEqual(worker.DEFAULT_REASONING_EFFORT, "high")
        self.assertEqual(worker.DEFAULT_TEMPERATURE, 1.0)
        self.assertEqual(worker.DEFAULT_TOP_P, 0.95)
        self.assertEqual(
            worker.CHAT_COMPLETIONS_ENDPOINT,
            "https://api.deepinfra.com/v1/openai/chat/completions",
        )
        self.assertEqual(
            worker.chat_completions_endpoint("https://example.invalid/root/"),
            "https://example.invalid/root/chat/completions",
        )

    def test_request_payload_uses_required_defaults(self) -> None:
        payload = worker.build_request_payload(self.prepared())
        self.assertEqual(payload["model"], worker.MODEL_ID)
        self.assertEqual(payload["reasoning_effort"], "high")
        self.assertEqual(payload["temperature"], 1.0)
        self.assertEqual(payload["top_p"], 0.95)
        self.assertEqual(payload["max_tokens"], worker.DEFAULT_MAX_TOKENS)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["role"], "user")

    def test_max_token_validation_is_bounded(self) -> None:
        for invalid in (0, -1, worker.MAX_OUTPUT_TOKENS + 1):
            with self.subTest(invalid=invalid), self.assertRaises(worker.WorkerError) as caught:
                worker.validate_max_tokens(invalid)
            self.assertEqual(caught.exception.code, "invalid_max_tokens")
        self.assertEqual(
            worker.validate_max_tokens(worker.MAX_OUTPUT_TOKENS),
            worker.MAX_OUTPUT_TOKENS,
        )


class ContextBoundaryTests(RepositoryFixture):
    def test_loads_only_explicit_context_files(self) -> None:
        self.write_text("src/selected.py", "VALUE = 7\n")
        self.write_text("src/neighbor.py", "MUST_NOT_BE_INCLUDED = True\n")
        prepared = worker.prepare_input(
            project_root=self.root,
            prompt="Read one file.",
            prompt_file=None,
            context_paths=[Path("src/selected.py")],
        )
        self.assertEqual([item.relative_path for item in prepared.context_files], ["src/selected.py"])
        self.assertEqual(prepared.context_files[0].text, "VALUE = 7\n")
        self.assertNotIn("neighbor", worker.build_user_message(prepared))

    def test_prompt_file_is_explicit_utf8_input(self) -> None:
        self.write_text("task.txt", "Explain the named symbol.\n")
        prepared = worker.prepare_input(
            project_root=self.root,
            prompt=None,
            prompt_file=Path("task.txt"),
            context_paths=[],
        )
        self.assertEqual(prepared.prompt_source, "task.txt")
        self.assertEqual(prepared.prompt, "Explain the named symbol.\n")

    def test_rejects_absolute_and_traversal_paths_outside_repository(self) -> None:
        outside_directory = Path(self.temporary.name).parent
        outside = outside_directory / f"outside-{Path(self.temporary.name).name}.txt"
        outside.write_text("outside", encoding="utf-8")
        self.addCleanup(outside.unlink)
        for requested in (outside, Path("..") / outside.name):
            with self.subTest(requested=requested), self.assertRaises(worker.WorkerError) as caught:
                worker.load_explicit_text_file(self.root, requested, byte_limit=1024)
            self.assertEqual(caught.exception.code, "outside_repository")

    def test_rejects_sensitive_extensions_and_generated_paths(self) -> None:
        cases = {
            "rom.nds": "sensitive_context_extension",
            "save.sav": "sensitive_context_extension",
            "slot.state": "sensitive_context_extension",
            "build/report.txt": "sensitive_context_path",
            "base/header.txt": "sensitive_context_path",
            "screenshots/frame.txt": "sensitive_context_path",
        }
        for relative, expected_code in cases.items():
            with self.subTest(relative=relative):
                self.write_text(relative, "not actually sensitive test data")
                with self.assertRaises(worker.WorkerError) as caught:
                    worker.load_explicit_text_file(self.root, Path(relative), byte_limit=1024)
                self.assertEqual(caught.exception.code, expected_code)

    def test_rejects_git_ignored_files(self) -> None:
        self.write_text(".gitignore", "*.log\n")
        self.write_text("private.log", "ignored local output\n")
        with self.assertRaises(worker.WorkerError) as caught:
            worker.load_explicit_text_file(self.root, Path("private.log"), byte_limit=1024)
        self.assertEqual(caught.exception.code, "git_ignored_context")

    def test_rejects_binary_content(self) -> None:
        for relative, data in (
            ("nul.txt", b"left\0right"),
            ("control.txt", b"left\x01right"),
            ("invalid.txt", b"\xff\xfe"),
        ):
            with self.subTest(relative=relative):
                self.write_bytes(relative, data)
                with self.assertRaises(worker.WorkerError) as caught:
                    worker.load_explicit_text_file(self.root, Path(relative), byte_limit=1024)
                self.assertEqual(caught.exception.code, "binary_context")

    def test_total_input_size_limit_includes_prompt_and_context(self) -> None:
        self.write_text("context.txt", "12345")
        with self.assertRaises(worker.WorkerError) as caught:
            worker.prepare_input(
                project_root=self.root,
                prompt="12345",
                prompt_file=None,
                context_paths=[Path("context.txt")],
                max_context_bytes=9,
            )
        self.assertEqual(caught.exception.code, "context_size_limit")


class RequestAndResponseTests(RepositoryFixture):
    def test_missing_token_fails_without_opening_network(self) -> None:
        calls = 0

        def opener(*args: object, **kwargs: object) -> FakeResponse:
            nonlocal calls
            calls += 1
            return FakeResponse(completion_response())

        result = worker.run_worker(self.prepared(), environment={}, opener=opener)
        self.assertFalse(result["success"])
        self.assertEqual(result["errors"][0]["code"], "missing_token")
        self.assertEqual(calls, 0)

    def test_dry_run_needs_no_token_and_does_not_open_network(self) -> None:
        def opener(*args: object, **kwargs: object) -> FakeResponse:
            self.fail("dry-run attempted network access")

        result = worker.run_worker(
            self.prepared(),
            environment={},
            opener=opener,
            dry_run=True,
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["dry_run"])
        self.assertIsNone(result["response"])

    def test_http_request_target_and_payload(self) -> None:
        captured: dict[str, object] = {}

        def opener(request: object, *, timeout: float) -> FakeResponse:
            captured["url"] = request.full_url
            captured["method"] = request.get_method()
            captured["authorization"] = request.get_header("Authorization")
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse(completion_response())

        result = worker.run_worker(
            self.prepared(),
            environment={worker.TOKEN_ENV_VAR: "unit-test-token"},
            opener=opener,
            timeout_seconds=12,
        )
        self.assertTrue(result["success"])
        self.assertEqual(captured["url"], worker.CHAT_COMPLETIONS_ENDPOINT)
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["authorization"], "Bearer unit-test-token")
        self.assertEqual(captured["payload"]["model"], worker.MODEL_ID)
        self.assertNotIn("unit-test-token", json.dumps(captured["payload"]))
        self.assertEqual(captured["payload"]["reasoning_effort"], "high")
        self.assertEqual(captured["timeout"], 12)

    def test_response_parsing_extracts_usage_and_cost(self) -> None:
        parsed = worker.parse_completion_response(completion_response())
        self.assertEqual(parsed["model_returned"], worker.MODEL_ID)
        self.assertEqual(parsed["prompt_tokens"], 11)
        self.assertEqual(parsed["completion_tokens"], 7)
        self.assertEqual(parsed["total_tokens"], 18)
        self.assertEqual(parsed["estimated_cost"], 0.000012)
        self.assertEqual(parsed["finish_reason"], "stop")
        self.assertEqual(parsed["response"], "analysis")

    def test_top_level_estimated_cost_is_preserved(self) -> None:
        response = completion_response(estimated_cost=None)
        response["estimated_cost"] = 0.125
        parsed = worker.parse_completion_response(response)
        self.assertEqual(parsed["estimated_cost"], 0.125)

    def test_returned_model_mismatch_is_a_failed_envelope(self) -> None:
        def opener(*args: object, **kwargs: object) -> FakeResponse:
            return FakeResponse(completion_response(model="deepseek-v4-flash"))

        result = worker.run_worker(
            self.prepared(),
            environment={worker.TOKEN_ENV_VAR: "unit-test-token"},
            opener=opener,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["model_returned"], "deepseek-v4-flash")
        self.assertEqual(result["errors"][0]["code"], "model_mismatch")

    def test_malformed_missing_and_unsuccessful_responses_fail(self) -> None:
        cases: list[tuple[object, str]] = [
            (b"not-json", "malformed_json"),
            ({"choices": []}, "missing_model"),
            ({"model": worker.MODEL_ID}, "missing_choices"),
            ({"success": False}, "provider_error"),
            (completion_response(finish_reason="error"), "unsuccessful_completion"),
        ]
        for payload, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                result = worker.run_worker(
                    self.prepared(),
                    environment={worker.TOKEN_ENV_VAR: "unit-test-token"},
                    opener=lambda *args, payload=payload, **kwargs: FakeResponse(payload),
                )
                self.assertFalse(result["success"])
                self.assertEqual(result["errors"][0]["code"], expected_code)

    def test_timeout_and_http_errors_are_structured(self) -> None:
        def timeout_opener(*args: object, **kwargs: object) -> FakeResponse:
            raise socket.timeout()

        timeout_result = worker.run_worker(
            self.prepared(),
            environment={worker.TOKEN_ENV_VAR: "unit-test-token"},
            opener=timeout_opener,
        )
        self.assertEqual(timeout_result["errors"][0]["code"], "timeout")

        for status in (400, 503):
            def http_opener(*args: object, status: int = status, **kwargs: object) -> FakeResponse:
                raise urllib.error.HTTPError(
                    worker.CHAT_COMPLETIONS_ENDPOINT,
                    status,
                    "failure",
                    {},
                    io.BytesIO(b'{"error":{"message":"rejected"}}'),
                )

            with self.subTest(status=status):
                result = worker.run_worker(
                    self.prepared(),
                    environment={worker.TOKEN_ENV_VAR: "unit-test-token"},
                    opener=http_opener,
                )
                self.assertFalse(result["success"])
                self.assertEqual(result["errors"][0]["code"], "http_error")
                self.assertEqual(result["errors"][0]["http_status"], status)

    def test_token_never_appears_in_serialized_result(self) -> None:
        secret = "secret-token-that-must-not-escape"

        def opener(*args: object, **kwargs: object) -> FakeResponse:
            return FakeResponse(completion_response(content=f"provider reflected {secret}"))

        result = worker.run_worker(
            self.prepared(),
            environment={worker.TOKEN_ENV_VAR: secret},
            opener=opener,
        )
        serialized = json.dumps(result, sort_keys=True)
        self.assertNotIn(secret, serialized)
        self.assertIn("[REDACTED]", serialized)

    def test_input_containing_token_is_refused_before_network(self) -> None:
        secret = "secret-token-in-input"
        calls = 0

        def opener(*args: object, **kwargs: object) -> FakeResponse:
            nonlocal calls
            calls += 1
            return FakeResponse(completion_response())

        result = worker.run_worker(
            self.prepared(prompt=f"Do not send {secret}"),
            environment={worker.TOKEN_ENV_VAR: secret},
            opener=opener,
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["errors"][0]["code"], "token_in_input")
        self.assertEqual(calls, 0)
        self.assertNotIn(secret, json.dumps(result, sort_keys=True))


@unittest.skipUnless(
    os.environ.get("DEEPSEEK_RUN_INTEGRATION") == "1"
    and bool(os.environ.get(worker.TOKEN_ENV_VAR)),
    "set DEEPSEEK_RUN_INTEGRATION=1 and DEEPINFRA_TOKEN for the live DeepInfra test",
)
class DeepInfraLiveIntegrationTests(unittest.TestCase):
    def test_exact_checkpoint_returns_a_tiny_marker(self) -> None:
        prepared = worker.prepare_input(
            project_root=worker.PROJECT_ROOT,
            prompt="Return exactly this marker and nothing else: DEEPSEEK_0731_OK",
            prompt_file=None,
            context_paths=[],
        )
        result = worker.run_worker(
            prepared,
            reasoning_effort="high",
            max_tokens=worker.DEFAULT_MAX_TOKENS,
            timeout_seconds=60,
        )
        self.assertTrue(result["success"], result["errors"])
        self.assertEqual(result["model_returned"], worker.MODEL_ID)
        self.assertEqual(result["reasoning_effort"], "high")
        self.assertTrue(str(result["response"]).strip())
        self.assertIn("DEEPSEEK_0731_OK", str(result["response"]))
        self.assertIs(type(result["prompt_tokens"]), int)
        self.assertGreater(result["prompt_tokens"], 0)
        self.assertIs(type(result["completion_tokens"]), int)
        self.assertGreater(result["completion_tokens"], 0)
        self.assertIs(type(result["total_tokens"]), int)
        self.assertGreater(result["total_tokens"], 0)
        self.assertEqual(
            result["total_tokens"],
            result["prompt_tokens"] + result["completion_tokens"],
        )
        self.assertIsInstance(result["estimated_cost"], (int, float))
        self.assertGreater(result["estimated_cost"], 0)
        self.assertNotIn(
            os.environ[worker.TOKEN_ENV_VAR],
            json.dumps(result, sort_keys=True),
        )


if __name__ == "__main__":
    unittest.main()
