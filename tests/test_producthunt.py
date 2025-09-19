from __future__ import annotations

import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ph_ai_tools import (
    AiTool,
    ProductHuntScrapeError,
    scrape_top_ai_tools,
)


FIXTURE_PATH = Path("tests/fixtures/sample_ai_topic.html")


class ProductHuntExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html = FIXTURE_PATH.read_text(encoding="utf-8")

    def test_scrape_top_ai_tools_from_fixture(self) -> None:
        tools = scrape_top_ai_tools(html=self.html, limit=5)
        self.assertEqual(len(tools), 5)
        self.assertEqual(
            [tool.name for tool in tools],
            ["AlphaMind", "BetaBuilder", "CreativeX", "DataPilot", "Explainify"],
        )
        self.assertEqual(tools[0].makers, ["Alice Smith", "Bob Jones"])
        self.assertEqual(tools[1].makers, ["Carol Lee"])
        self.assertEqual(tools[2].makers, ["Dan Miller", "Eva Green"])
        self.assertEqual(tools[3].makers, ["Frank Hall"])
        self.assertEqual(tools[4].makers, ["Grace Kim"])
        self.assertEqual(tools[0].product_hunt_url, "https://www.producthunt.com/posts/alphamind")
        self.assertEqual(tools[0].external_url, "https://alphamind.ai")
        self.assertEqual(tools[1].external_url, "https://betabuilder.example.com")
        self.assertEqual(tools[3].external_url, "https://datapilot.app")
        self.assertTrue(all(tool.votes_count is not None for tool in tools))
        self.assertGreater(tools[0].votes_count, tools[-1].votes_count)

    def test_limit_zero_returns_empty_list(self) -> None:
        tools = scrape_top_ai_tools(html=self.html, limit=0)
        self.assertEqual(tools, [])

    def test_missing_payload_raises_error(self) -> None:
        with self.assertRaises(ProductHuntScrapeError):
            scrape_top_ai_tools(html="<html></html>")


class AiToolModelTests(unittest.TestCase):
    def test_to_dict_contains_optional_fields(self) -> None:
        tool = AiTool(
            name="Sample",
            tagline="Tagline",
            makers=["Maker"],
            product_hunt_url="https://www.producthunt.com/posts/sample",
            external_url="https://example.com",
            votes_count=123,
        )
        self.assertEqual(
            tool.to_dict(),
            {
                "name": "Sample",
                "tagline": "Tagline",
                "makers": ["Maker"],
                "product_hunt_url": "https://www.producthunt.com/posts/sample",
                "external_url": "https://example.com",
                "votes_count": 123,
            },
        )


if __name__ == "__main__":
    unittest.main()
