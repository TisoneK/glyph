"""Live-capture CLI wiring — testable without Playwright installed.

The live browser run itself needs the `live` extra and a network target,
so it isn't unit-tested here; these cover the plumbing: subcommand
registration, the GLYPH_PROXY fallback, and graceful degradation when
Playwright is missing.
"""
from __future__ import annotations

import importlib.util

import pytest

from glyph.cli import _live_kwargs, build_parser, main

_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None


def test_capture_live_registered_with_defaults():
    args = build_parser().parse_args(
        ["capture", "live", "https://x.test", "--db", "/tmp/x.db"])
    assert args.func.__name__ == "run_live"
    assert args.func.__module__.endswith("cli.capture")
    assert args.url == "https://x.test"
    assert args.explore == 2 and args.settle_ms == 3000 and args.timeout_ms == 30000


def test_run_live_registered():
    args = build_parser().parse_args(["run", "live", "https://y.test", "--explore", "5"])
    assert args.func.__name__ == "run_live"
    assert args.func.__module__.endswith("cli.run")
    assert args.explore == 5


def test_proxy_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("GLYPH_PROXY", "http://env-proxy:8080")
    args = build_parser().parse_args(["capture", "live", "https://x.test"])
    assert _live_kwargs(args)["proxy"] == "http://env-proxy:8080"


def test_explicit_proxy_overrides_env(monkeypatch):
    monkeypatch.setenv("GLYPH_PROXY", "http://env-proxy:8080")
    args = build_parser().parse_args(
        ["capture", "live", "https://x.test", "--proxy", "http://flag:9090"])
    assert _live_kwargs(args)["proxy"] == "http://flag:9090"


@pytest.mark.skipif(_PLAYWRIGHT, reason="Playwright installed — can't test the missing-dep path")
def test_graceful_without_playwright(tmp_path, capsys):
    rc = main(["capture", "live", "https://x.invalid", "--db", str(tmp_path / "c.db")])
    assert rc == 1
    assert "Playwright" in capsys.readouterr().err
