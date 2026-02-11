import * as path from "path";
import * as url from "url";
import * as cdk from "aws-cdk-lib";
import * as iam from "aws-cdk-lib/aws-iam";
import * as agentcore from "@aws-cdk/aws-bedrock-agentcore-alpha";
import type { IUserPool, IUserPoolClient } from "aws-cdk-lib/aws-cognito";
import type * as s3 from "aws-cdk-lib/aws-s3";

// ESモジュールで__dirnameを取得
const __filename = url.fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface AgentRuntimeProps {
  stack: cdk.Stack;
  userPool?: IUserPool;
  userPoolClient?: IUserPoolClient;
  bucket: s3.IBucket;
  nameSuffix?: string;
}

export function createAgentRuntime({
  stack,
  userPool,
  userPoolClient,
  bucket,
  nameSuffix,
}: AgentRuntimeProps) {
  // sandbox: ローカルビルド
  const agentRuntimeArtifact = agentcore.AgentRuntimeArtifact.fromAsset(
    path.join(__dirname, "runtime"),
  );

  // JWT 認証設定（Cognito）
  const discoveryUrl = userPool
    ? `https://cognito-idp.${stack.region}.amazonaws.com/${userPool.userPoolId}/.well-known/openid-configuration`
    : undefined;

  const authConfig =
    discoveryUrl && userPoolClient
      ? agentcore.RuntimeAuthorizerConfiguration.usingJWT(discoveryUrl, [
          userPoolClient.userPoolClientId,
        ])
      : undefined;

  // Runtime 名（環境ごとに分離）
  const runtimeName = nameSuffix
    ? `presentation_review_agent_${nameSuffix}`
    : "presentation_review_agent";

  // AgentCore Runtime 作成
  const runtime = new agentcore.Runtime(
    stack,
    "PresentationReviewAgentRuntime",
    {
      runtimeName,
      agentRuntimeArtifact: agentRuntimeArtifact,
      authorizerConfiguration: authConfig,
      environmentVariables: {
        S3_BUCKET_NAME: bucket.bucketName,
      },
    },
  );

  // Bedrock InvokeModel 権限
  runtime.addToRolePolicy(
    new iam.PolicyStatement({
      actions: [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
      ],
      resources: [
        "arn:aws:bedrock:*::foundation-model/*",
        "arn:aws:bedrock:*:*:inference-profile/*",
      ],
    }),
  );

  // S3 アクセス権限
  runtime.addToRolePolicy(
    new iam.PolicyStatement({
      actions: ["s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      resources: [bucket.bucketArn, `${bucket.bucketArn}/*`],
    }),
  );

  // Transcribe 権限
  runtime.addToRolePolicy(
    new iam.PolicyStatement({
      actions: [
        "transcribe:StartTranscriptionJob",
        "transcribe:GetTranscriptionJob",
      ],
      resources: ["*"],
    }),
  );

  // 出力
  new cdk.CfnOutput(stack, "AgentRuntimeArn", {
    value: runtime.agentRuntimeArn,
    description: "Presentation Review Agent Runtime ARN",
  });

  return { runtime };
}
