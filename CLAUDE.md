# CLAUDE.md

このファイルは、このリポジトリで作業する Claude Code (claude.ai/code) へのガイダンスを提供します。

## コマンド

```bash
uv sync              # 依存関係のインストール
make run             # Bot 起動（macOS Keychain から OAuth トークン自動取得）
make dev             # python -m で起動（entrypoint.sh を経由しない）
make lint            # ruff check src/
make fmt             # ruff format src/
make fix             # ruff check --fix src/
make check           # lint + フォーマットチェック
make test            # pytest

make docker-run      # Docker でビルド & 起動（デタッチ、Keychain トークン注入）
make docker-stop     # コンテナ停止
make docker-logs     # Bot ログをテール
```

単一テストの実行: `uv run pytest tests/path/to/test_file.py::test_name`

## アーキテクチャ

```
Slack → bot.py → agent.py (SessionManager) → Claude Agent SDK → Slack 返信
```

**`bot.py`** — `slack_bolt`（非同期）を使った Slack イベントハンドラ。2つのイベントを処理する:
- `app_mention`: スレッドのセッションを開始または再開してメッセージを処理
- `message`: すでにアクティブなセッションがあるスレッドへのフォローアップメッセージに応答

両ハンドラとも処理中は `:eyes:` リアクションを付け、返信後に外す。長いレスポンスは改行境界で 3900 文字以下のチャンクに分割して送信する。

**`agent.py`** — `SessionManager` が Slack の `thread_ts` → `ClaudeSDKClient` をマッピングする。スレッドごとに独立した Claude Agent SDK セッションを保持する。セッションは `SESSION_TTL_SECONDS`（デフォルト 1800 秒）で期限切れになり、5 分ごとのクリーンアップで削除される。`setting_sources=["user"]` を指定しているため、ユーザーの `~/.claude/` のスキルと設定を自動で読み込む。

**`config.py`** — 全設定を環境変数から読み込む。`SLACK_BOT_TOKEN` と `SLACK_APP_TOKEN` は起動時に必須。

**`main.py`** — ロギングを他のモジュールインポートより先に設定する（意図的な `E402` ruff 無視）。`AsyncSocketModeHandler` を定期クリーンアップコルーチンと共に実行する。

## Docker

Docker イメージは以下を行う:
1. npm 経由で Claude Code CLI (`@anthropic-ai/claude-code`) をインストール
2. `gogcli`（Google Workspace CLI）をインストール
3. `xcnkx/dotfiles` をクローンして `~/.claude/`（スキル、コマンド、設定、CLAUDE.md）を Bot ユーザーのホームにコピー
4. コンテナ起動時、`entrypoint.sh` が `GOG_TOKEN_WORK` / `GOG_TOKEN_PERSONAL` 環境変数からファイルベースのキーリングに gogcli トークンをインポートして Bot を起動

必須の実行時環境変数: `SLACK_BOT_TOKEN`、`SLACK_APP_TOKEN`、そして `CLAUDE_CODE_OAUTH_TOKEN` か `ANTHROPIC_API_KEY` のいずれか。

## 主要な依存関係

- `claude-agent-sdk` — Claude Agent SDK（`ClaudeSDKClient`、`ClaudeAgentOptions`）
- `slack-bolt` — Slack イベントフレームワーク（非同期モード）
- `python-dotenv` — `.env` ファイルの読み込み
- `ruff` — リンター兼フォーマッター（Python 3.12 ターゲット）
- `pytest-asyncio`（`asyncio_mode = "auto"` で設定済み）
