"""CLI integration coverage for the scrape_artfinder application."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional

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
        **_: Any,
    ) -> None:
        self.listing_url = listing_url
        self.jsonl_path = jsonl_path or Path("artfinder_scraper/data/artworks.jsonl")
        self.rate_limit_seconds = rate_limit_seconds
        self.errors: list[Any] = []
        self._captured_limits: List[Optional[int]] = []

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


def test_run_command_reports_errors(monkeypatch) -> None:
    def factory(**kwargs: Any) -> DummyErrorRunner:
        return DummyErrorRunner(**kwargs)

    monkeypatch.setattr(scrape_artfinder, "ScraperRunner", factory)

    result = CliRunner().invoke(scrape_artfinder.app, ["run", "--limit", "0"])

    assert result.exit_code == 0
    assert "Encountered the following errors:" in result.stderr
    assert "[extract]" in result.stderr
