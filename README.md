# claude-sdk-slack-bot

Claude Agent SDK を使った Slack Bot。`~/.claude/skills/` のスキルを Slack から実行できる。

## 特徴

- **スキル自動発見**: `~/.claude/skills/` のスキルを自動で認識・実行
- **マルチスレッド会話**: Slack スレッドごとに独立したセッションを維持
- **OAuth トークン自動取得**: macOS Keychain から Claude Code の認証トークンを自動抽出

## アーキテクチャ

```
Slack (Socket Mode)
  ↓ @mention / スレッド返信
Slack Bot (slack_bolt)
  ↓ thread_ts でセッション管理
SessionManager (thread_ts → ClaudeSDKClient)
  ↓
Claude Agent SDK → Skills 自動実行
  ↓
Slack スレッドに返信
```

## セットアップ

### 前提条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)
- `claude login` 済み

### Slack App 作成

1. [Slack API](https://api.slack.com/apps) で新しいアプリを作成
2. **Socket Mode** を有効化 → App-Level Token (`xapp-...`) を取得
3. **OAuth & Permissions** で Bot Token Scopes を追加:
   - `app_mentions:read`
   - `chat:write`
   - `reactions:read`
   - `reactions:write`
4. ワークスペースにインストール → Bot User OAuth Token (`xoxb-...`) を取得
5. **Event Subscriptions** で以下を購読:
   - `app_mention`
   - `message.channels`

### 環境変数

```bash
cp .env.example .env
```

`.env` を編集:

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-level-token
```

### 起動

```bash
# 依存関係インストール
uv sync

# 起動（OAuth トークンは Keychain から自動取得）
make run
```

## 使い方

Slack で Bot にメンションすると応答する:

```
@bot 今日の予定をSlackに報告して
@bot 使えるスキルを教えて
@bot このコードをレビューして
```

同じスレッド内でメンションなしで会話を続けられる。

## Docker

```bash
# ローカルの Keychain からトークンを取得して起動
make docker-run

# クラウドデプロイ時は環境変数で渡す
docker compose run --rm \
  -e CLAUDE_CODE_OAUTH_TOKEN=... \
  bot
```

## 設定

| 環境変数 | デフォルト | 説明 |
|---|---|---|
| `SLACK_BOT_TOKEN` | (必須) | Slack Bot User OAuth Token |
| `SLACK_APP_TOKEN` | (必須) | Slack App-Level Token (Socket Mode) |
| `CLAUDE_CODE_OAUTH_TOKEN` | Keychain から自動取得 | Claude Code OAuth トークン |
| `ANTHROPIC_API_KEY` | - | API キー認証（OAuth の代替） |
| `ALLOWED_TOOLS` | `Skill,Read,Bash,...` | 許可するツール（カンマ区切り） |
| `PERMISSION_MODE` | `bypassPermissions` | Agent SDK パーミッションモード |
| `SESSION_TTL_SECONDS` | `1800` | セッション TTL（秒） |
| `MAX_TURNS` | `30` | エージェントの最大ターン数 |

## 開発

```bash
make dev      # 開発モードで起動
make lint     # リンター実行
make fmt      # フォーマッター実行
make check    # lint + format チェック
make test     # テスト実行
```
