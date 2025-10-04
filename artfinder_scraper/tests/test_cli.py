"""CLI integration coverage for the scrape_artfinder application."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Sequence

from typer.testing import CliRunner

import scrape_artfinder


class DummyRunner:
    """Test double that mimics :class:`ScraperRunner` construction and execution."""

    def __init__(
        self,
        *,
        listing_url: str,
        jsonl_path: Optional[Path],
        rate_limit_seconds: float,
        skip_slugs: Sequence[str] | None = None,
        persist_outputs: bool = True,
        **_: Any,
    ) -> None:
        self.listing_url = listing_url
        self.jsonl_path = jsonl_path or Path("artfinder_scraper/data/artworks.jsonl")
        self.rate_limit_seconds = rate_limit_seconds
        self.errors: list[Any] = []
        self._captured_limits: List[Optional[int]] = []
        self.skip_slugs = list(skip_slugs or [])
        self.persist_outputs = persist_outputs

    def run(self, *, max_items: Optional[int] = None) -> list[object]:
        self._captured_limits.append(max_items)
        return [object() for _ in range(max_items or 0)]


class DummyErrorRunner(DummyRunner):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.errors = [
            type("Err", (), {"stage": "extract", "product_url": "https://example.com/", "message": "failure"})()
        ]


def test_run_command_invokes_runner_with_options(monkeypatch, tmp_path) -> None:
    invoked: dict[str, Any] = {}

    def factory(**kwargs: Any) -> DummyRunner:
        runner = DummyRunner(**kwargs)
        invoked.update(
            {
                "listing_url": runner.listing_url,
                "jsonl_path": runner.jsonl_path,
                "rate_limit": runner.rate_limit_seconds,
                "runner": runner,
                "persist_outputs": runner.persist_outputs,
                "skip_slugs": runner.skip_slugs,
            }
        )
        return runner

    monkeypatch.setattr(scrape_artfinder, "ScraperRunner", factory)

    jsonl_target = tmp_path / "artworks.jsonl"

    result = CliRunner().invoke(
        scrape_artfinder.app,
        [
            "run",
            "--limit",
            "2",
            "--listing-url",
            "https://example.com/listing/",
            "--jsonl-path",
            str(jsonl_target),
            "--rate-limit",
            "0.75",
        ],
    )

    assert result.exit_code == 0
    assert "Processed 2 artwork(s);" in result.stdout
    assert invoked["listing_url"] == "https://example.com/listing/"
    assert invoked["jsonl_path"] == jsonl_target
    assert invoked["rate_limit"] == 0.75
    assert invoked["runner"]._captured_limits == [2]
    assert invoked["persist_outputs"] is True
    assert invoked["skip_slugs"] == []


def test_run_command_reports_errors(monkeypatch) -> None:
    def factory(**kwargs: Any) -> DummyErrorRunner:
        return DummyErrorRunner(**kwargs)

    monkeypatch.setattr(scrape_artfinder, "ScraperRunner", factory)

    result = CliRunner().invoke(scrape_artfinder.app, ["run", "--limit", "0"])

    assert result.exit_code == 0
    assert "Encountered the following errors:" in result.stderr
    assert "[extract]" in result.stderr


def test_run_command_dry_run(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    def factory(**kwargs: Any) -> DummyRunner:
        runner = DummyRunner(**kwargs)
        captured.update(
            {
                "persist_outputs": runner.persist_outputs,
            }
        )
        return runner

    monkeypatch.setattr(scrape_artfinder, "ScraperRunner", factory)

    result = CliRunner().invoke(scrape_artfinder.app, ["run", "--dry-run", "--limit", "1"])

    assert result.exit_code == 0
    assert "dry-run mode" in result.stdout
    assert captured["persist_outputs"] is False


def test_resume_command_loads_slugs(monkeypatch, tmp_path) -> None:
    jsonl_path = tmp_path / "artworks.jsonl"

    loaded_paths: list[Path] = []

    def fake_load(path: Path) -> set[str]:
        loaded_paths.append(path)
        return {"one", "two"}

    observed: dict[str, Any] = {}

    def factory(**kwargs: Any) -> DummyRunner:
        runner = DummyRunner(**kwargs)
        observed.update(
            {
                "skip_slugs": runner.skip_slugs,
                "jsonl_path": runner.jsonl_path,
            }
        )
        return runner

    monkeypatch.setattr(scrape_artfinder, "ScraperRunner", factory)

    monkeypatch.setattr(scrape_artfinder, "_load_processed_slugs", fake_load)

    result = CliRunner().invoke(
        scrape_artfinder.app,
        [
            "resume",
            "--jsonl-path",
            str(jsonl_path),
            "--limit",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "Loaded 2 processed slug" in result.stdout
    assert sorted(observed["skip_slugs"]) == ["one", "two"]
    assert observed["jsonl_path"] == jsonl_path
    assert loaded_paths == [jsonl_path]
