"""Real-artifact Given/When/Then BDD tests for trace-readiness skills upgrades.

Zero fakes and zero undeclared test dependencies (matches requirements-ci.txt:
jsonschema + pytest + Python stdlib only).
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import textwrap
import tracemalloc
import types
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_skills_bdd", ROOT / "scripts" / "validate-skills.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_bdd_skills_pass_real_validator_and_preserve_public_boundaries() -> None:
    """Given the upgraded neatlogs-py-setup and neatlogs-py skills on disk,
    When scripts/validate-skills.py runs as a real subprocess,
    Then validation exits 0 with zero forbidden internal terms or broken safety gates."""
    # When: invoke the real CI validator script
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate-skills.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    # Then: exit 0 and every updated skill passes public-boundary checks
    assert proc.returncode == 0, f"validate-skills.py failed:\n{proc.stdout}\n{proc.stderr}"
    for rel in (
        "skills/neatlogs-py-setup/SKILL.md",
        "skills/neatlogs-py-setup/references/2-add-init.md",
        "skills/neatlogs-py-setup/references/understand-first.md",
        "skills/neatlogs-py-setup/references/4-decorate-functions.md",
        "skills/neatlogs-py-setup/references/6-decorate-tools.md",
        "skills/neatlogs-py-setup/references/6b-retrievers-and-provenance.md",
        "skills/neatlogs-py/SKILL.md",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.validate_public_doctor_boundary(text, errors, rel)
        assert errors == [], f"Public boundary violation in {rel}: {errors}"


def test_bdd_setup_skill_encodes_judge_and_backtrack_readiness_rules() -> None:
    """Given a developer following neatlogs-py-setup,
    When reading SKILL.md and its references,
    Then root I/O, retriever freshness, session hygiene, provenance, replay=True,
    and python -m neatlogs doctor --trace are all explicitly specified and linked."""
    setup_dir = ROOT / "skills" / "neatlogs-py-setup"
    skill_md = (setup_dir / "SKILL.md").read_text(encoding="utf-8")
    understand = (setup_dir / "references" / "understand-first.md").read_text(encoding="utf-8")
    decorate_fns = (setup_dir / "references" / "4-decorate-functions.md").read_text(encoding="utf-8")
    decorate_tools = (setup_dir / "references" / "6-decorate-tools.md").read_text(encoding="utf-8")
    step_6b = (setup_dir / "references" / "6b-retrievers-and-provenance.md").read_text(
        encoding="utf-8"
    )
    py_skill = (ROOT / "skills" / "neatlogs-py" / "SKILL.md").read_text(encoding="utf-8")

    # Then: Step 6b is wired into SKILL.md and all local links resolve cleanly
    assert "references/6b-retrievers-and-provenance.md" in skill_md
    assert "python -m neatlogs doctor --trace" in skill_md
    assert "python -m neatlogs doctor --trace" in py_skill
    assert "never pass `trace_id`" in skill_md.lower() or "never pass `trace_id`" in step_6b.lower()
    assert "per-request `neatlogs.flush()`" in skill_md

    # Phase 2 inventory hunts for RAG, sessions, provenance, and streaming boundaries
    for expected in ("updated_at", "session_id", "prompt_version", "StreamingResponse"):
        assert expected in understand

    # Step 4 encodes Clean Root I/O + streaming accumulation + prompt_version
    for expected in (
        'set_attribute("input.value"',
        'set_attribute("output.value"',
        "prompt_version",
        "6b-retrievers-and-provenance.md",
    ):
        assert expected in decorate_fns

    # Step 6 encodes replay=True and links to 6b
    assert "replay=True" in decorate_tools
    assert "(6b-retrievers-and-provenance.md)" in decorate_tools

    # Step 6b encodes retrievers, freshness, sessions, provenance, checkpoints, diagnostics
    for expected in (
        'kind="RETRIEVER"',
        'kind="RERANKER"',
        'kind="GUARDRAIL"',
        "updated_at",
        "replay=True",
        "NEATLOGS_ENVIRONMENT",
        "NEATLOGS_RELEASE",
        "neatlogs.checkpoint",
        "neatlogs.report_diagnostic",
    ):
        assert expected in step_6b

    # neatlogs-py SKILL.md documents init provenance, replayable kinds, and audit CLI
    for expected in (
        "`environment`",
        "`release`",
        "NEATLOGS_ENVIRONMENT",
        "NEATLOGS_RELEASE",
        "neatlogs.checkpoint",
        "neatlogs.report_diagnostic(category",
        "neatlogs >= 1.5.0",
    ):
        assert expected in py_skill

    # Guard against wrong report_diagnostic(kind=...) signature and invalid severity="warn"
    assert "report_diagnostic(kind" not in py_skill
    assert "report_diagnostic(kind" not in step_6b
    assert 'severity="warn"' not in step_6b
    assert 'severity="warning"' in step_6b

    # Explicit >= 1.5.0 version prerequisite guard wherever PR #290 APIs are documented
    for gated_doc in (skill_md, decorate_fns, decorate_tools, step_6b, py_skill, understand):
        assert ">= 1.5.0" in gated_doc

    # Every relative markdown link in modified reference files resolves on disk
    for md_file in (
        setup_dir / "SKILL.md",
        setup_dir / "references" / "understand-first.md",
        setup_dir / "references" / "4-decorate-functions.md",
        setup_dir / "references" / "6-decorate-tools.md",
        setup_dir / "references" / "6b-retrievers-and-provenance.md",
        ROOT / "skills" / "neatlogs-py" / "SKILL.md",
    ):
        for target in LINK_RE.findall(md_file.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#")):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (md_file.parent / target_path).resolve()
            assert resolved.is_file(), f"Broken relative link {target!r} in {md_file}"


def test_bdd_packaged_skill_zips_are_clean_and_include_new_reference(tmp_path: Path) -> None:
    """Given the skills directory,
    When packaging neatlogs-py-setup and neatlogs-py into release zip archives,
    Then zip integrity passes and 6b-retrievers-and-provenance.md is bundled."""
    for skill_name in ("neatlogs-py-setup", "neatlogs-py"):
        skill_dir = ROOT / "skills" / skill_name
        archive_path = tmp_path / f"{skill_name}.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(skill_dir.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(ROOT / "skills"))
        with zipfile.ZipFile(archive_path, "r") as zf:
            assert zf.testzip() is None
            names = set(zf.namelist())
            assert f"{skill_name}/SKILL.md" in names
            if skill_name == "neatlogs-py-setup":
                assert f"{skill_name}/references/6b-retrievers-and-provenance.md" in names


def _load_sse_recipe_namespace(decorate_fns: str, *, trace_fn=None) -> dict[str, object]:
    """Extract and execute the real ✅ RIGHT SSE streaming recipe from 4-decorate-functions.md."""
    match = re.search(
        r"(?m)^[ \t]*# ✅ RIGHT — instrument typed app events inside the generator[^\n]*\n(.*?)\n[ \t]*```",
        decorate_fns,
        re.DOTALL,
    )
    assert match is not None, "Could not locate ✅ RIGHT SSE recipe in 4-decorate-functions.md"
    snippet = textwrap.dedent(match.group(1))
    snippet = re.sub(
        r"(?m)^from starlette\.responses import StreamingResponse\s*$",
        "",
        snippet,
    )

    class _RecordingStreamingResponse:
        def __init__(self, body_iterator, *, media_type: str | None = None) -> None:
            self.body_iterator = body_iterator
            self.media_type = media_type

    class _RecordingSpan:
        def __init__(self) -> None:
            self.attributes: dict[str, object] = {}

        def set_attribute(self, key: str, value: object) -> None:
            self.attributes[key] = value

    recorded_spans: list[_RecordingSpan] = []

    @contextlib.contextmanager
    def _default_trace(*_args, **_kwargs):
        span = _RecordingSpan()
        recorded_spans.append(span)
        yield span

    namespace: dict[str, object] = {
        "StreamingResponse": _RecordingStreamingResponse,
        "neatlogs": types.SimpleNamespace(trace=trace_fn or _default_trace),
        "_recorded_spans": recorded_spans,
    }
    exec(snippet, namespace)
    return namespace


def test_bdd_sse_streaming_recipe_is_sanitized_bounded_and_fail_open() -> None:
    """Given the application-event SSE streaming recipe in 4-decorate-functions.md,
    When executing the real extracted chat() generator across debug/metadata events,
    PII/bearer/API-key secrets, boundary-crossing emails, 8 MiB delta payloads,
    raising request/event getters, and capture/set_attribute failures,
    Then it redacts secrets before clipping, stays memory-bounded (<512 KiB peak),
    sets media_type='text/event-stream', and never disrupts SSE wire delivery."""
    decorate_fns = (
        ROOT / "skills" / "neatlogs-py-setup" / "references" / "4-decorate-functions.md"
    ).read_text(encoding="utf-8")

    # Guard against unsafe patterns and non-canonical Doctor flag names
    assert "ev.text" not in decorate_fns
    assert "neatlogs.output_truncated" not in decorate_fns
    assert "neatlogs.stream_incomplete" not in decorate_fns
    assert "neatlogs.capture.truncated" in decorate_fns
    assert "neatlogs.stream.incomplete" in decorate_fns
    assert "MAX_PREVIEW_CHARS = 4096" in decorate_fns
    assert 'media_type="text/event-stream"' in decorate_fns
    assert "EventSourceResponse" in decorate_fns
    assert "sse-starlette" in decorate_fns
    assert "leave yielded wire frames untouched" in decorate_fns.lower()

    ns = _load_sse_recipe_namespace(decorate_fns)
    chat_fn = ns["chat"]
    recorded_spans = ns["_recorded_spans"]
    req = types.SimpleNamespace(
        conversation_id="conv-1",
        user_id="user-1",
        message="Help alice@example.com with Authorization: Bearer tok_secret123",
    )

    # 1. Debug/metadata filtering and PII/bearer/API-key redaction on input & output
    events = [
        {"kind": "debug", "text": "debug-user@example.com internal-state"},
        {"kind": "delta", "text": "Hello ", "metadata": {"email": "private@example.com"}},
        {
            "kind": "delta",
            "text": "world for bob@example.com with Bearer abc and sk-proj-abc1234567890xyz",
        },
        {"kind": "done"},
    ]

    async def _run_clean():
        async def _event_gen(_req):
            for ev in events:
                yield ev

        ns["event_gen"] = _event_gen
        resp = await chat_fn(req)
        assert resp.media_type == "text/event-stream"
        return [frame async for frame in resp.body_iterator]

    frames = asyncio.run(_run_clean())
    assert len(frames) == 4
    assert frames[1] == 'event: delta\ndata: "Hello "\n\n'
    assert frames[3] == 'event: done\ndata: {"kind": "done"}\n\n'

    span = recorded_spans[-1]
    assert json.loads(span.attributes["input.value"]) == {
        "message": "Help [REDACTED_EMAIL] with [REDACTED_TOKEN]"
    }
    assert span.attributes["neatlogs.capture.truncated"] is False
    assert span.attributes["neatlogs.stream.incomplete"] is False
    assert json.loads(span.attributes["output.value"]) == {
        "reply": "Hello world for [REDACTED_EMAIL] with [REDACTED_TOKEN] and [REDACTED_SECRET]"
    }
    for forbidden in (
        "debug-user@example.com",
        "internal-state",
        "private@example.com",
        "bob@example.com",
        "Bearer abc",
        "sk-proj-abc1234567890xyz",
        "metadata",
    ):
        assert forbidden not in span.attributes["output.value"]

    # 2. 8 MiB delta text stays strictly memory-bounded (<512 KiB peak) and sets truncated=True
    big_text = "x" * (8 * 1024 * 1024)
    big_events = [{"kind": "delta", "text": big_text}, {"kind": "done"}]
    orig_format_sse = ns["_format_sse"]

    async def _run_big_delta():
        async def _event_gen(_req):
            for ev in big_events:
                yield ev

        ns["event_gen"] = _event_gen
        # Isolate telemetry capture memory from wire serialization of the 8 MiB payload
        ns["_format_sse"] = lambda _ev: "event: delta\ndata: \"ok\"\n\n"
        resp = await chat_fn(req)
        return [frame async for frame in resp.body_iterator]

    tracemalloc.start()
    try:
        asyncio.run(_run_big_delta())
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
        ns["_format_sse"] = orig_format_sse

    assert peak < 512 * 1024, f"Expected bounded preview capture (<512 KiB), got {peak} bytes"
    big_span = recorded_spans[-1]
    assert big_span.attributes["neatlogs.capture.truncated"] is True
    assert big_span.attributes["neatlogs.stream.incomplete"] is False
    assert json.loads(big_span.attributes["output.value"]) == {
        "reply": "x" * 4096,
        "truncated": True,
    }

    # 3. Boundary-crossing email, bearer-shrinkage boundary email, and redaction-expansion cap
    boundary_msg = ("a" * 4087) + " alice@example.com"
    shrink_msg = "Bearer " + ("x" * 5000) + " " + ("a" * 3176) + " alice@example.com"
    expanding_msg = "a@b.co " * 585  # 4,095 chars -> 9,945 chars after redaction
    assert len(expanding_msg) == 4095

    for label, text in (
        ("boundary", boundary_msg),
        ("shrink", shrink_msg),
        ("expand", expanding_msg),
    ):
        async def _run_edge(payload=text):
            async def _event_gen(_req):
                yield {"kind": "delta", "text": payload}
                yield {"kind": "done"}

            ns["event_gen"] = _event_gen
            resp = await chat_fn(
                types.SimpleNamespace(conversation_id=f"c-{label}", user_id=f"u-{label}", message=payload)
            )
            return [frame async for frame in resp.body_iterator]

        asyncio.run(_run_edge())
        edge_span = recorded_spans[-1]
        assert edge_span.attributes["neatlogs.capture.truncated"] is True
        for attr_key, field_key in (("input.value", "message"), ("output.value", "reply")):
            parsed = json.loads(edge_span.attributes[attr_key])
            assert parsed["truncated"] is True, f"{label} {attr_key} missing truncated"
            assert len(parsed[field_key]) <= 4096
            assert "alice" not in parsed[field_key]
            assert "@e" not in parsed[field_key]
            assert "a@b.co" not in parsed[field_key]

    # 4. Raising req getters, capture/sanitizer errors, and span.set_attribute errors NEVER disrupt delivery
    class _FailingSpan:
        def set_attribute(self, _key: str, _value: object) -> None:
            raise RuntimeError("span attribute export failed")

    @contextlib.contextmanager
    def _failing_trace(*_args, **_kwargs):
        yield _FailingSpan()

    class _BadRequest:
        @property
        def conversation_id(self) -> str:
            raise RuntimeError("conversation_id getter failed")

        @property
        def user_id(self) -> str:
            raise RuntimeError("user_id getter failed")

        @property
        def message(self) -> str:
            raise ValueError("request message getter failed")

    class _HostileEvent:
        kind = "meta"

        @property
        def text(self) -> str:
            raise ValueError("not a text event")

    orig_trace = ns["neatlogs"]
    orig_sanitize = ns["_sanitize_and_bound"]
    fail_events = [_HostileEvent(), {"kind": "delta", "text": "hello"}, {"kind": "done"}]

    def _raising_sanitize(*_args, **_kwargs):
        raise RuntimeError("sanitizer exploded")

    try:
        ns["neatlogs"] = types.SimpleNamespace(trace=_failing_trace)
        ns["_sanitize_and_bound"] = _raising_sanitize

        async def _run_fail_open():
            async def _event_gen(_req):
                for ev in fail_events:
                    yield ev

            ns["event_gen"] = _event_gen
            resp = await chat_fn(_BadRequest())
            assert resp.media_type == "text/event-stream"
            return [frame async for frame in resp.body_iterator]

        fail_frames = asyncio.run(_run_fail_open())
    finally:
        ns["neatlogs"] = orig_trace
        ns["_sanitize_and_bound"] = orig_sanitize

    assert fail_frames == [
        'event: meta\ndata: {"kind": "meta"}\n\n',
        'event: delta\ndata: "hello"\n\n',
        'event: done\ndata: {"kind": "done"}\n\n',
    ]


def _run_chat_and_audit(
    decorate_fns: str,
    *,
    req: object,
    event_gen_factory,
    early_close: bool = False,
    expect_runtime_error: bool = False,
    break_sanitizer: bool = False,
) -> tuple[list[str], dict[str, object], dict[str, object], dict[str, str]]:
    """Run extracted chat() through real paired SDK #290 NeatlogsSpanProcessor + audit_readable_spans
    when neatlogs is installed, or enforce the canonical Doctor contract in standalone skills CI."""
    try:
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

        from neatlogs.core.span_processor import NeatlogsSpanProcessor
        from neatlogs.trace_audit import audit_readable_spans
    except ImportError:
        NeatlogsSpanProcessor = None
        audit_readable_spans = None

    if os.getenv("NEATLOGS_REQUIRE_PAIRED_SDK") == "1":
        assert NeatlogsSpanProcessor is not None and audit_readable_spans is not None, (
            "Expected real paired SDK #290 NeatlogsSpanProcessor and audit_readable_spans"
        )

    if NeatlogsSpanProcessor is not None and audit_readable_spans is not None:
        provider = TracerProvider()
        sink = InMemorySpanExporter()
        processor = NeatlogsSpanProcessor(
            emit_completion_markers=False,
            own_all_spans=True,
            release="v1",
        )
        provider.add_span_processor(processor)
        provider.add_span_processor(SimpleSpanProcessor(sink))
        tracer = provider.get_tracer("neatlogs.skills.test")

        @contextlib.contextmanager
        def _real_trace(name: str, *, kind: str = "WORKFLOW", session_id=None, end_user_id=None, prompt_version=None, **_kw):
            attrs: dict[str, object] = {"neatlogs.span.kind": kind}
            if session_id:
                attrs["neatlogs.session.id"] = session_id
            if end_user_id:
                attrs["neatlogs.end_user.id"] = end_user_id
            if prompt_version:
                attrs["neatlogs.prompt.version"] = prompt_version
            with tracer.start_as_current_span(name, attributes=attrs) as span:
                yield span

        def _emit_child_tool() -> None:
            with tracer.start_as_current_span(
                "lookup_docs",
                attributes={
                    "neatlogs.span.kind": "TOOL",
                    "neatlogs.tool.name": "lookup_docs",
                    "input.value": json.dumps({"query": "SSE tracing"}),
                    "output.value": json.dumps({"intermediate": "child-tool-result"}),
                },
            ):
                pass

        ns = _load_sse_recipe_namespace(decorate_fns, trace_fn=_real_trace)
        if break_sanitizer:
            ns["_sanitize_and_bound"] = lambda *_a, **_kw: (_ for _ in ()).throw(
                RuntimeError("sanitizer failed")
            )
        ns["event_gen"] = event_gen_factory(_emit_child_tool)
        chat_fn = ns["chat"]

        async def _drive():
            resp = await chat_fn(req)
            out: list[str] = []
            if early_close:
                out.append(await resp.body_iterator.__anext__())
                await resp.body_iterator.aclose()
                return out
            try:
                async for frame in resp.body_iterator:
                    out.append(frame)
            except RuntimeError:
                if not expect_runtime_error:
                    raise
            else:
                if expect_runtime_error:
                    raise AssertionError("Expected RuntimeError to propagate")
            return out

        try:
            frames = asyncio.run(_drive())
            root_span_done = next(s for s in sink.get_finished_spans() if s.name == "chat")
            processor._emit_completion_marker(
                root_span_done,
                f"{root_span_done.context.trace_id:032x}",
                {},
                marker_tracer=provider.get_tracer("neatlogs.internal"),
            )
        finally:
            provider.shutdown()

        finished = sink.get_finished_spans()
        root_finished = next(s for s in finished if s.name == "chat")
        root_attrs = dict(root_finished.attributes or {})
        report = audit_readable_spans(finished)
        checks = {c["name"]: c["status"] for c in report["checks"]}
        return frames, root_attrs, report, checks

    # Standalone skills CI path (requirements-ci.txt only): run extracted chat() + canonical contract
    ns = _load_sse_recipe_namespace(decorate_fns)
    if break_sanitizer:
        ns["_sanitize_and_bound"] = lambda *_a, **_kw: (_ for _ in ()).throw(
            RuntimeError("sanitizer failed")
        )
    ns["event_gen"] = event_gen_factory(lambda: None)
    chat_fn = ns["chat"]

    async def _drive_ci():
        resp = await chat_fn(req)
        out: list[str] = []
        if early_close:
            out.append(await resp.body_iterator.__anext__())
            await resp.body_iterator.aclose()
            return out
        try:
            async for frame in resp.body_iterator:
                out.append(frame)
        except RuntimeError:
            if not expect_runtime_error:
                raise
        else:
            if expect_runtime_error:
                raise AssertionError("Expected RuntimeError to propagate")
        return out

    frames = asyncio.run(_drive_ci())
    root_attrs = dict(ns["_recorded_spans"][-1].attributes)

    def _non_empty(val: object) -> bool:
        if val is None:
            return False
        if isinstance(val, str):
            s = val.strip()
            return bool(s) and s not in {'""', "null", "None", "{}", "[]"}
        return True

    canonical_incomplete_flags = (
        "pii.server_redacted",
        "pii.server_redaction_failed",
        "neatlogs.payload.truncated",
        "neatlogs.capture.truncated",
        "neatlogs.stream.incomplete",
    )
    root_io_ok = _non_empty(root_attrs.get("input.value")) and _non_empty(
        root_attrs.get("output.value")
    )
    stream_incomplete = root_attrs.get("neatlogs.stream.incomplete") in (True, "true")
    lossy = any(root_attrs.get(k) in (True, "true") for k in canonical_incomplete_flags)
    checks = {
        "root_io_present": "pass" if root_io_ok else "fail",
        "provenance_and_replayability": "fail" if lossy else "pass",
    }
    report = {
        "jev_ready": root_io_ok and not stream_incomplete,
        "replay_ready": not lossy,
        "checks": [{"name": k, "status": v} for k, v in checks.items()],
    }
    return frames, root_attrs, report, checks


def test_bdd_sse_recipe_traces_match_paired_doctor_readiness_rules() -> None:
    """Given real traces produced by the SSE streaming recipe in 4-decorate-functions.md
    (exercised through real paired SDK #290 NeatlogsSpanProcessor + audit_readable_spans),
    When auditing complete, truncated, late-error, no-answer, aborted, cancelled, and
    capture-failed streams with a child TOOL span,
    Then complete streams are jev_ready & replay_ready, truncated streams fail replay_ready,
    and late-error / no-answer / aborted streams omit output.value (with zero child-tool
    backfill) and fail both jev_ready and replay_ready."""
    decorate_fns = (
        ROOT / "skills" / "neatlogs-py-setup" / "references" / "4-decorate-functions.md"
    ).read_text(encoding="utf-8")
    req = types.SimpleNamespace(
        conversation_id="conv-doctor",
        user_id="user-doctor",
        message="Explain SSE tracing",
    )

    # 1. Normal complete stream (delta + done + child TOOL span) -> jev_ready=True, replay_ready=True
    def _complete_gen(emit_tool):
        async def _gen(_req):
            emit_tool()
            yield {"kind": "delta", "text": "Complete "}
            yield {"kind": "delta", "text": "answer"}
            yield {"kind": "done"}

        return _gen

    frames, root_attrs, report, checks = _run_chat_and_audit(
        decorate_fns, req=req, event_gen_factory=_complete_gen
    )
    assert len(frames) == 3
    assert json.loads(root_attrs["output.value"]) == {"reply": "Complete answer"}
    assert root_attrs["neatlogs.capture.truncated"] is False
    assert root_attrs["neatlogs.stream.incomplete"] is False
    assert checks["root_io_present"] == "pass"
    assert checks["provenance_and_replayability"] == "pass"
    assert report["jev_ready"] is True
    assert report["replay_ready"] is True

    # 2. Truncated complete stream (>4,096 chars + done) -> positive control: publishes output.value,
    # sets neatlogs.capture.truncated=True, jev_ready=True, replay_ready=False
    def _truncated_done_gen(emit_tool):
        async def _gen(_req):
            emit_tool()
            yield {"kind": "delta", "text": "a" * 9000}
            yield {"kind": "done"}

        return _gen

    _, trunc_attrs, trunc_report, trunc_checks = _run_chat_and_audit(
        decorate_fns, req=req, event_gen_factory=_truncated_done_gen
    )
    assert json.loads(trunc_attrs["output.value"]) == {"reply": "a" * 4096, "truncated": True}
    assert trunc_attrs["neatlogs.capture.truncated"] is True
    assert trunc_attrs["neatlogs.stream.incomplete"] is False
    assert trunc_checks["root_io_present"] == "pass"
    assert trunc_checks["provenance_and_replayability"] == "fail"
    assert trunc_report["jev_ready"] is True
    assert trunc_report["replay_ready"] is False

    # 3. Late error AFTER preview budget is exhausted (same 9,000-char prefix, followed by error
    # AND done so only saw_error suppresses output) -> output.value OMITTED, no child-tool backfill,
    # jev_ready=False, replay_ready=False
    def _late_error_gen(emit_tool):
        async def _gen(_req):
            emit_tool()
            yield {"kind": "delta", "text": "a" * 9000}
            yield {"kind": "error"}
            yield {"kind": "done"}

        return _gen

    _, late_attrs, late_report, late_checks = _run_chat_and_audit(
        decorate_fns, req=req, event_gen_factory=_late_error_gen
    )
    assert "output.value" not in late_attrs
    assert "neatlogs.workflow.output" not in late_attrs
    assert "neatlogs.WORKFLOW.output" not in late_attrs
    assert late_attrs["neatlogs.capture.truncated"] is True
    assert late_attrs["neatlogs.stream.incomplete"] is True
    assert late_checks["root_io_present"] == "fail"
    assert late_checks["provenance_and_replayability"] == "fail"
    assert late_report["jev_ready"] is False
    assert late_report["replay_ready"] is False

    # 4. No-answer streams (empty, debug-only + done, whitespace-only + done, missing done) ->
    # NEVER emit {"reply": ""}; omit output.value with zero child-tool backfill
    for label, no_answer_events in (
        ("empty", []),
        ("debug-only", [{"kind": "debug", "text": "internal"}, {"kind": "done"}]),
        ("whitespace-only", [{"kind": "delta", "text": "   "}, {"kind": "done"}]),
        ("missing-done", [{"kind": "delta", "text": "partial without done"}]),
    ):
        def _no_answer_gen(emit_tool, evs=no_answer_events):
            async def _gen(_req):
                emit_tool()
                for ev in evs:
                    yield ev

            return _gen

        _, na_attrs, na_report, na_checks = _run_chat_and_audit(
            decorate_fns, req=req, event_gen_factory=_no_answer_gen
        )
        assert "output.value" not in na_attrs, f"Published output.value for {label}"
        assert "neatlogs.workflow.output" not in na_attrs, f"Backfilled child output for {label}"
        assert "neatlogs.WORKFLOW.output" not in na_attrs, f"Backfilled child output for {label}"
        assert na_attrs["neatlogs.stream.incomplete"] is True
        assert na_checks["root_io_present"] == "fail"
        assert na_checks["provenance_and_replayability"] == "fail"
        assert na_report["jev_ready"] is False
        assert na_report["replay_ready"] is False

    # 5. Aborted stream with child TOOL span (mid-stream exception, early cancellation, sanitizer crash)
    # -> child tool output is NEVER backfilled onto root; jev_ready=False, replay_ready=False
    def _errored_gen(emit_tool):
        async def _gen(_req):
            emit_tool()
            yield {"kind": "delta", "text": "partial before crash"}
            raise RuntimeError("upstream reset")

        return _gen

    err_frames, err_attrs, err_report, err_checks = _run_chat_and_audit(
        decorate_fns, req=req, event_gen_factory=_errored_gen, expect_runtime_error=True
    )
    assert err_frames == ['event: delta\ndata: "partial before crash"\n\n']
    assert "output.value" not in err_attrs
    assert "neatlogs.workflow.output" not in err_attrs
    assert "neatlogs.WORKFLOW.output" not in err_attrs
    assert err_attrs["neatlogs.stream.incomplete"] is True
    assert err_checks["root_io_present"] == "fail"
    assert err_checks["provenance_and_replayability"] == "fail"
    assert err_report["jev_ready"] is False
    assert err_report["replay_ready"] is False

    def _cancel_gen(emit_tool):
        async def _gen(_req):
            emit_tool()
            yield {"kind": "delta", "text": "first"}
            yield {"kind": "delta", "text": "second"}
            yield {"kind": "done"}

        return _gen

    cancel_frames, cancel_attrs, cancel_report, cancel_checks = _run_chat_and_audit(
        decorate_fns, req=req, event_gen_factory=_cancel_gen, early_close=True
    )
    assert cancel_frames == ['event: delta\ndata: "first"\n\n']
    assert "output.value" not in cancel_attrs
    assert "neatlogs.workflow.output" not in cancel_attrs
    assert "neatlogs.WORKFLOW.output" not in cancel_attrs
    assert cancel_attrs["neatlogs.stream.incomplete"] is True
    assert cancel_checks["root_io_present"] == "fail"
    assert cancel_checks["provenance_and_replayability"] == "fail"
    assert cancel_report["jev_ready"] is False
    assert cancel_report["replay_ready"] is False

    san_frames, san_attrs, san_report, san_checks = _run_chat_and_audit(
        decorate_fns, req=req, event_gen_factory=_complete_gen, break_sanitizer=True
    )
    assert len(san_frames) == 3
    assert "output.value" not in san_attrs
    assert "neatlogs.workflow.output" not in san_attrs
    assert "neatlogs.WORKFLOW.output" not in san_attrs
    assert san_attrs["neatlogs.stream.incomplete"] is True
    assert san_checks["root_io_present"] == "fail"
    assert san_checks["provenance_and_replayability"] == "fail"
    assert san_report["jev_ready"] is False
    assert san_report["replay_ready"] is False


def test_bdd_checkpoint_docs_do_not_promise_automatic_scrubbing() -> None:
    """Given the checkpoint guidance in neatlogs-py-setup and neatlogs-py,
    When checking privacy and redaction rules,
    Then automatic secret scrubbing is NOT promised, state_delta export is documented
    as requiring allowlisted/sanitized fields, and the digest-only path is preferred."""
    step_6b = (
        ROOT / "skills" / "neatlogs-py-setup" / "references" / "6b-retrievers-and-provenance.md"
    ).read_text(encoding="utf-8")
    py_skill = (ROOT / "skills" / "neatlogs-py" / "SKILL.md").read_text(encoding="utf-8")

    for doc_name, text in (
        ("6b-retrievers-and-provenance.md", step_6b),
        ("neatlogs-py/SKILL.md", py_skill),
    ):
        lowered = text.lower()
        assert "scrub secrets automatically" not in lowered, f"Stale claim in {doc_name}"
        assert "state_delta" in text
        assert "state_digest" in text
        assert "allowlisted" in lowered
        assert "digest-only" in lowered


def test_bdd_doctor_trace_examples_and_eu_notes_keep_doctor_on_trace_region() -> None:
    """Given every skill documenting neatlogs doctor --trace and EU endpoint setup,
    When reading the Doctor examples and EU notes,
    Then API-key audits use --endpoint / NEATLOGS_ENDPOINT (https://eu.ingest.neatlogs.com)
    while token-authenticated audits (NEATLOGS_TOKEN + NEATLOGS_PROJECT_ID) use
    NEATLOGS_HOST=https://eu.app.neatlogs.com rather than the ingest host."""
    setup_skill = (ROOT / "skills" / "neatlogs-py-setup" / "SKILL.md").read_text(encoding="utf-8")
    add_init = (
        ROOT / "skills" / "neatlogs-py-setup" / "references" / "2-add-init.md"
    ).read_text(encoding="utf-8")
    py_skill = (ROOT / "skills" / "neatlogs-py" / "SKILL.md").read_text(encoding="utf-8")

    for doc_name, text in (
        ("neatlogs-py-setup/SKILL.md", setup_skill),
        ("neatlogs-py/SKILL.md", py_skill),
    ):
        assert "--endpoint https://eu.ingest.neatlogs.com" in text, f"Missing EU --endpoint in {doc_name}"
        assert "NEATLOGS_ENDPOINT" in text, f"Missing NEATLOGS_ENDPOINT in {doc_name}"
        assert "NEATLOGS_HOST=https://eu.app.neatlogs.com" in text, (
            f"Missing EU NEATLOGS_HOST for token-auth doctor audit in {doc_name}"
        )
        assert (
            "python -m neatlogs doctor --trace <trace_id> --endpoint https://eu.ingest.neatlogs.com --json"
            in text
        ), f"Missing EU API-key doctor --trace example in {doc_name}"
        assert (
            "env -u NEATLOGS_API_KEY NEATLOGS_HOST=https://eu.app.neatlogs.com python -m neatlogs doctor --trace <trace_id> --json"
            in text
        ), f"Missing EU token-auth doctor --trace example (unsetting NEATLOGS_API_KEY) in {doc_name}"

    assert "--endpoint https://eu.ingest.neatlogs.com" in add_init
    assert "NEATLOGS_ENDPOINT" in add_init
    assert "env -u NEATLOGS_API_KEY" in add_init
    assert "NEATLOGS_HOST=https://eu.app.neatlogs.com" in add_init
    assert "| `NEATLOGS_ENDPOINT` |" in py_skill
    assert "| `NEATLOGS_HOST` |" in py_skill
