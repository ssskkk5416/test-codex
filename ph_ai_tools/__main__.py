"""Command line entry-point for extracting Product Hunt AI tool listings."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .producthunt import (
    DEFAULT_LIMIT,
    DEFAULT_TIMEOUT,
    DEFAULT_TOPIC_SLUG,
    AiTool,
    ProductHuntScrapeError,
    scrape_top_ai_tools,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Product HuntからAIツールの一覧 (上位順) を抽出し、概要と開発元情報を表示します。"
        )
    )
    parser.add_argument(
        "--topic",
        default=DEFAULT_TOPIC_SLUG,
        help="Product Huntのトピックスラッグ (デフォルト: artificial-intelligence)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help="取得するAIツールの件数",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="ページ取得時のタイムアウト秒数",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="出力フォーマット (text または json)",
    )
    parser.add_argument(
        "--html-file",
        type=Path,
        help="ローカルHTMLファイルを解析する場合に指定します (ネットワークアクセス不要)",
    )

    args = parser.parse_args(argv)

    html_payload: str | None = None
    if args.html_file:
        try:
            html_payload = args.html_file.read_text(encoding="utf-8")
        except OSError as exc:
            parser.exit(1, f"HTMLファイルの読み込みに失敗しました: {exc}\n")

    try:
        tools = scrape_top_ai_tools(
            topic_slug=args.topic,
            limit=args.limit,
            html=html_payload,
            timeout=args.timeout,
        )
    except ProductHuntScrapeError as exc:
        parser.exit(1, f"抽出中にエラーが発生しました: {exc}\n")

    if args.format == "json":
        print(json.dumps([tool.to_dict() for tool in tools], ensure_ascii=False, indent=2))
    else:
        _print_text(tools)

    return 0


def _print_text(tools: Sequence[AiTool]) -> None:
    for index, tool in enumerate(tools, start=1):
        makers = ", ".join(tool.makers) if tool.makers else "不明"
        print(f"{index}. {tool.name}")
        if tool.tagline:
            print(f"   概要: {tool.tagline}")
        else:
            print("   概要: (情報なし)")
        print(f"   開発元: {makers}")
        print(f"   Product Hunt: {tool.product_hunt_url}")
        if tool.external_url:
            print(f"   公式サイト: {tool.external_url}")
        if tool.votes_count is not None:
            print(f"   投票数: {tool.votes_count}")
        if index != len(tools):
            print()


if __name__ == "__main__":
    sys.exit(main())
