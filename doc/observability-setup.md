# AgentCore Observability（トレーシング）設定ガイド

AgentCore Runtime のリクエスト処理フロー（LLM 呼び出し、ツール実行、レイテンシ等）を CloudWatch GenAI Observability ダッシュボードと X-Ray で可視化する。

## 概要

| レイヤー | 変更内容 | 効果 |
|---|---|---|
| アプリ側 | ADOT（AWS Distro for OpenTelemetry）による自動計装 | LLM 呼び出し・ツール実行のスパンを自動取得 |
| インフラ側 | CDK でトレース・ログ配信を設定 | CloudWatch / X-Ray にテレメトリデータを送信 |

テレメトリの階層構造:

```
Session（ユーザー↔エージェントの会話単位）
  └── Trace（単一のリクエスト-レスポンスサイクル）
        └── Span（ツール呼び出し・LLM推論などの個別処理）
```

## 1. 事前準備（1回限り）

### X-Ray トレース送信先の設定

CloudShell または AWS CLI で以下を実行（アカウント × リージョンごとに1回）:

```bash
# トレース送信先を CloudWatch Logs に設定
aws xray update-trace-segment-destination --destination CloudWatchLogs --region us-east-1

# CloudWatch Logs にリソースポリシーを追加（X-Ray からの書き込みを許可）
aws logs put-resource-policy \
  --policy-name AgentCoreXRayAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Sid": "TransactionSearchXRayAccess",
      "Effect": "Allow",
      "Principal": {"Service": "xray.amazonaws.com"},
      "Action": "logs:PutLogEvents",
      "Resource": [
        "arn:aws:logs:us-east-1:<ACCOUNT_ID>:log-group:aws/spans:*",
        "arn:aws:logs:us-east-1:<ACCOUNT_ID>:log-group:/aws/application-signals/data:*"
      ]
    }]
  }' \
  --region us-east-1
```

### サンプリング率の変更（任意）

デフォルトではサンプリングされるため、全トレースを取得したい場合:

```bash
aws xray update-indexing-rule --name "Default" \
  --rule '{"Probabilistic": {"DesiredSamplingPercentage": 100}}' \
  --region us-east-1
```

## 2. アプリ側の変更

### 2.1 requirements.txt

```diff
  bedrock-agentcore
  boto3
  botocore[crt]
  python-dotenv
- strands-agents
+ strands-agents[otel]
+ aws-opentelemetry-distro
```

- `strands-agents[otel]`: Strands Agent の OpenTelemetry 計装を有効化
- `aws-opentelemetry-distro`: ADOT Python ディストリビューション（X-Ray へのトレース送信）

### 2.2 Dockerfile

```diff
  FROM python:3.12-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  EXPOSE 8080
- CMD ["python", "main.py"]
+ CMD ["opentelemetry-instrument", "python", "main.py"]
```

`opentelemetry-instrument` コマンドが自動的にスパンを取得し、X-Ray にエクスポートする。

## 3. インフラ側の変更（CDK）

### 3.1 agent/resource.ts に追加

`createAgentRuntime` 関数内に以下のリソースを追加する:

```typescript
import * as logs from "aws-cdk-lib/aws-logs";

// --- Observability: トレース配信 ---

// トレース配信ソース（AgentCore Runtime → X-Ray）
const traceSource = new logs.CfnDeliverySource(stack, "TraceSource", {
  name: `${runtimeName}-traces-source`,
  logType: "TRACES",
  resourceArn: runtime.agentRuntimeArn,
});

// トレース配信先（X-Ray）
const traceDest = new logs.CfnDeliveryDestination(stack, "TraceDest", {
  name: `${runtimeName}-traces-dest`,
  deliveryDestinationType: "XRAY",
});

// トレース配信を接続
const traceDelivery = new logs.CfnDelivery(stack, "TraceDelivery", {
  deliverySourceName: traceSource.ref,
  deliveryDestinationArn: traceDest.attrArn,
});
traceDelivery.addDependency(traceSource);
traceDelivery.addDependency(traceDest);

// --- Observability: ログ配信 ---

// ロググループ
const logGroup = new logs.LogGroup(stack, "AgentLogGroup", {
  logGroupName: `/aws/vendedlogs/bedrock-agentcore/${runtimeName}`,
  retention: logs.RetentionDays.ONE_MONTH,
  removalPolicy: cdk.RemovalPolicy.DESTROY,
});

// ログ配信ソース（AgentCore Runtime → CloudWatch Logs）
const logSource = new logs.CfnDeliverySource(stack, "LogSource", {
  name: `${runtimeName}-logs-source`,
  logType: "APPLICATION_LOGS",
  resourceArn: runtime.agentRuntimeArn,
});

// ログ配信先（CloudWatch Logs）
const logDest = new logs.CfnDeliveryDestination(stack, "LogDest", {
  name: `${runtimeName}-logs-dest`,
  deliveryDestinationType: "CWL",
  deliveryDestinationConfiguration: {
    destinationResourceArn: logGroup.logGroupArn,
  },
});

// ログ配信を接続
const logDelivery = new logs.CfnDelivery(stack, "LogDelivery", {
  deliverySourceName: logSource.ref,
  deliveryDestinationArn: logDest.attrArn,
});
logDelivery.addDependency(logSource);
logDelivery.addDependency(logDest);

// --- X-Ray 書き込み権限 ---
runtime.addToRolePolicy(
  new iam.PolicyStatement({
    actions: ["xray:PutTraceSegments", "xray:PutTelemetryRecords"],
    resources: ["*"],
  }),
);
```

> **Note**: CDK L2 コンストラクトへの Observability 統合は開発中（[Issue #36596](https://github.com/aws/aws-cdk/issues/36596)）。将来的にはより簡潔な API で設定できるようになる見込み。

## 4. デプロイと検証

### 4.1 デプロイ

```bash
cd frontend
npx ampx sandbox
```

### 4.2 動作確認

1. フロントエンドから音声ファイルをアップロードして分析を実行
2. 以下のコンソールで確認:
   - **CloudWatch → GenAI Observability** — セッション・トレース・スパンの可視化
   - **CloudWatch → ログ** — `/aws/vendedlogs/bedrock-agentcore/<runtimeName>` にログが出力されているか
   - **X-Ray → トレース** — サービスマップ・トレース詳細

### 4.3 確認できるメトリクス

| メトリクス | 場所 |
|---|---|
| セッション数・レイテンシ・エラー率 | CloudWatch GenAI Observability ダッシュボード |
| LLM 推論のトークン使用量 | トレース → スパン詳細 |
| ツール呼び出しの所要時間 | トレース → スパン詳細 |
| 分散トレーシング・サービスマップ | X-Ray コンソール |

## 参考リンク

- [AgentCore Observability 公式ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability.html)
- [Observability 設定方法](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html)
- [AgentCore と X-Ray](https://docs.aws.amazon.com/xray/latest/devguide/xray-services-agentcore.html)
- [AgentCore と CloudWatch](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/AgentCore-Agents.html)
- [Observability Quickstart（Starter Toolkit）](https://aws.github.io/bedrock-agentcore-starter-toolkit/user-guide/observability/quickstart.html)
