# 価格テーブル更新ガイド

このドキュメントでは、Bedrock モデル料金が改定された際の `PRICING` テーブル更新手順を説明します。

## 料金の確認方法

### 1. AWS Bedrock 料金ページ

https://aws.amazon.com/bedrock/pricing/

ページ内の「On-Demand pricing」セクションで、使用中のモデルの Input / Output 料金（per 1M tokens）を確認します。

### 2. Cross-Region Inference の料金

本プロジェクトでは Cross-Region Inference（モデルID が `us.` プレフィックス）を使用しています。
料金ページの「Cross-region inference」タブを確認してください。通常、オンデマンド料金と同額ですが、変更がないか確認が必要です。

## PRICING テーブルの更新手順

### 対象ファイル

`backend/tools/cost_tracker.py`

### 手順

1. 上記の料金ページで最新の Input / Output 料金を確認
2. `PRICING` 辞書の該当モデルの `input_per_1m` と `output_per_1m` を更新
3. `PRICING_VERSION` を更新日（`YYYY-MM-DD` 形式）に変更

```python
PRICING: dict[str, dict[str, float]] = {
    "us.anthropic.claude-sonnet-4-5-20250929-v1:0": {
        "input_per_1m": 3.0,      # ← 最新料金に更新
        "output_per_1m": 15.0,     # ← 最新料金に更新
    },
    "us.anthropic.claude-haiku-4-5-20251001-v1:0": {
        "input_per_1m": 0.80,      # ← 最新料金に更新
        "output_per_1m": 4.0,      # ← 最新料金に更新
    },
}

PRICING_VERSION = "2026-02-10"  # ← 更新日に変更
```

## 新モデル追加時の手順

新しい Claude モデルに切り替える場合、以下の複数ファイルを更新する必要があります。

### 1. モデルID の変更

| ファイル | 変数 | 説明 |
|---|---|---|
| `backend/agents/orchestrator.py` | `SONNET_MODEL_ID` | Orchestrator が使用するモデル |
| `backend/agents/speech_analyzer.py` | `HAIKU_MODEL_ID` | Speech Analyzer が使用するモデル |
| `backend/agents/content_analyzer.py` | `HAIKU_MODEL_ID` | Content Analyzer が使用するモデル |

### 2. 料金テーブルへの追加

`backend/tools/cost_tracker.py` の `PRICING` 辞書に新モデルのエントリを追加します。

```python
PRICING: dict[str, dict[str, float]] = {
    # 既存エントリ...
    "us.anthropic.claude-new-model-v1:0": {
        "input_per_1m": X.XX,
        "output_per_1m": XX.XX,
    },
}
```

### 3. PRICING_VERSION の更新

`PRICING_VERSION` を更新日に変更します。

### 4. Bedrock モデルアクセスの有効化

AWS コンソールの Bedrock > Model access で、新モデルのアクセスを有効にしてください。
