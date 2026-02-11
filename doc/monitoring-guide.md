# CloudWatch モニタリングガイド

AgentCore Runtime は ECS/Fargate 上で動作し、stdout/stderr が自動的に CloudWatch Logs に送信されます。
本プロジェクトでは JSON 構造化ログを出力しているため、CloudWatch Logs Insights で効率的に分析できます。

## ログ構造

各ログエントリは以下の JSON 形式で出力されます。

```json
{
  "timestamp": "2026-02-10T12:34:56.789+00:00",
  "level": "INFO",
  "logger": "__main__",
  "message": "分析完了",
  "run_id": "8a6f6d7d-...",
  "owner_sub": "9d1f...c3",
  "elapsed_seconds": 45.32,
  "total_cost_usd": 0.0178,
  "cached_transcript": false
}
```

## CloudWatch Logs Insights クエリ例

### リクエスト数（直近24時間）

```
fields @timestamp, run_id, owner_sub
| filter message = "分析リクエスト受付"
| stats count() as request_count by bin(1h)
| sort @timestamp desc
```

### エラー率

```
fields @timestamp, level, message
| filter level = "ERROR"
| stats count() as error_count by bin(1h)
```

### 平均処理時間

```
fields @timestamp, run_id, elapsed_seconds
| filter message = "分析完了"
| stats avg(elapsed_seconds) as avg_seconds, max(elapsed_seconds) as max_seconds, count() as total by bin(1h)
```

### コスト集計

```
fields @timestamp, run_id, total_cost_usd
| filter message = "分析完了"
| stats sum(total_cost_usd) as total_cost, avg(total_cost_usd) as avg_cost, count() as runs by bin(1d)
```

### 失敗した分析の詳細

```
fields @timestamp, run_id, owner_sub, message
| filter level = "ERROR"
| sort @timestamp desc
| limit 20
```

## ダッシュボード作成手順

1. AWS コンソール → CloudWatch → ダッシュボード → 「ダッシュボードの作成」
2. ダッシュボード名: `presentation-review-agent`
3. 以下のウィジェットを追加:

| ウィジェットタイプ | 内容 | クエリ |
|---|---|---|
| 数値 | 直近24h リクエスト数 | リクエスト数クエリ |
| 折れ線グラフ | 時間別リクエスト数 | リクエスト数クエリ |
| 折れ線グラフ | 平均処理時間 | 平均処理時間クエリ |
| 数値 | 直近24h エラー数 | エラー率クエリ |
| 数値 | 日次コスト | コスト集計クエリ |

## ロググループ

AgentCore デプロイ後のロググループ名は AgentCore の設定によります。
通常 `/aws/ecs/presentation-review-agent` のような形式です。
