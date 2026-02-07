# Python Dev Container テンプレート

uv + ruff を使った Python 開発用の Dev Container テンプレートです。
AWS Bedrock / Strands Agents を使った AI Agent 開発向けの依存関係が含まれています。

## 使い方

### 新規プロジェクトを作成

```bash
gh repo create my-new-project --private --template ryuki-imachi/python-devcontainer-template --clone
cd my-new-project
code .
```

VS Code で開いたら、左下の `><` → **「Reopen in Container」** を選択。

### 既存プロジェクトに追加

```bash
# .devcontainer フォルダをコピー
cp -r /path/to/python-devcontainer-template/.devcontainer ./
```

## 含まれるもの

- **Dockerfile**: Python 3.12 + uv
- **devcontainer.json**: VS Code 設定、拡張機能、AWS認証マウント
- **pyproject.toml**: uv 用の基本設定 + AI Agent 開発用依存関係

### デフォルトの依存関係

- `bedrock-agentcore` - AWS Bedrock Agent Core
- `boto3` / `botocore[crt]` - AWS SDK
- `strands-agents` - Strands Agents フレームワーク
- `python-dotenv` - 環境変数管理

## AWS 認証

ホストの `~/.aws` がコンテナにマウントされます。
コンテナ内で `aws sso login` を実行してブラウザ認証してください。

## パッケージ管理

```bash
# 依存関係を追加
uv add requests

# 開発用依存関係を追加
uv add --dev pytest

# 依存関係をインストール
uv sync
```

## カスタマイズ

### Python バージョンを変更

`.devcontainer/Dockerfile` の1行目を編集：

```dockerfile
FROM mcr.microsoft.com/devcontainers/python:3.13
```

### VS Code 拡張機能を追加

`.devcontainer/devcontainer.json` の `extensions` に追加：

```json
"extensions": [
  "ms-python.python",
  "charliermarsh.ruff",
  "amazonwebservices.aws-toolkit-vscode"
]
```
