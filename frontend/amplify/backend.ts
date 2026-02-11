import { defineBackend } from "@aws-amplify/backend";
import { auth } from "./auth/resource";
import { storage } from "./storage/resource";
import { createAgentRuntime } from "./agent/resource";

const backend = defineBackend({
  auth,
  storage,
});

// AgentCore スタックを作成
const agentStack = backend.createStack("AgentCoreStack");

// Cognito リソースを取得
const { userPool, userPoolClient } =
  backend.auth.resources.userPool && backend.auth.resources.userPoolClient
    ? {
        userPool: backend.auth.resources.userPool,
        userPoolClient: backend.auth.resources.userPoolClient,
      }
    : { userPool: undefined, userPoolClient: undefined };

// S3 バケットを取得
const bucket = backend.storage.resources.bucket;

// sandbox 環境の nameSuffix を取得
const isSandbox = !process.env.AWS_BRANCH;
const nameSuffix = isSandbox
  ? (
      backend.stack.node.tryGetContext("amplify-backend-name") as
        | string
        | undefined
    )?.replace(/[^a-zA-Z0-9_]/g, "_")
  : process.env.AWS_BRANCH?.replace(/[^a-zA-Z0-9_]/g, "_");

// AgentCore Runtime をデプロイ
const { runtime } = createAgentRuntime({
  stack: agentStack,
  userPool,
  userPoolClient,
  bucket,
  nameSuffix,
});

// フロントエンドに Runtime ARN を渡す
backend.addOutput({
  custom: {
    agentRuntimeArn: runtime.agentRuntimeArn,
  },
});
