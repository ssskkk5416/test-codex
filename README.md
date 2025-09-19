# Product Hunt AI Tool Extractor

このリポジトリは、Product Hunt に掲載されている AI ツールのうち、指定したトピックにおける上位のプロダクト情報を抽出する Python 製の簡易ツールです。CLI から実行すると、各ツールの概要・開発元・Product Hunt のリンク (および可能であれば公式サイト) を一覧表示します。

> **注意**: この環境では Product Hunt へのネットワークアクセスが制限されており、実際のページ取得は失敗する可能性があります。その場合は `--html-file` オプションを使ってローカルに保存した HTML を解析してください。

## セットアップ

Python 3.11 以上がインストールされていれば追加の依存関係は必要ありません。

```bash
python -m venv .venv
source .venv/bin/activate
```

(テストを実行するだけであれば仮想環境は必須ではありません。)

## 使い方

### 最新の Product Hunt から取得

```bash
python -m ph_ai_tools --topic artificial-intelligence --limit 5
```

上記コマンドは Product Hunt の「Artificial Intelligence」トピックから上位 5 件を取得し、テキスト形式で表示します。JSON 形式で出力したい場合は `--format json` を指定してください。

### ローカル HTML を解析

ネットワークが利用できない場合は、あらかじめダウンロードした HTML ファイルを以下のように指定できます。

```bash
python -m ph_ai_tools --html-file path/to/sample.html --limit 5
```

## テストの実行

リポジトリ直下で次のコマンドを実行します。

```bash
python -m unittest discover -s tests -p "test*.py"
```

## プロジェクト構成

- `ph_ai_tools/` – 抽出処理および CLI エントリーポイント
- `tests/` – フィクスチャと単体テスト
- `tests/fixtures/sample_ai_topic.html` – テスト用に用意した Product Hunt トピックページのサンプル HTML

## ライセンス

このプロジェクトは MIT ライセンスで提供されています。
