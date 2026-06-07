"""CloudWatch Logs 向け JSON 構造化ログ設定"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """ログレコードを JSON 1行に整形するフォーマッター"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # extra フィールドをマージ（logging 標準属性は除外）
        standard_attrs = logging.LogRecord("", 0, "", 0, None, None, None).__dict__.keys()
        for key, value in record.__dict__.items():
            if key not in standard_attrs and key not in log_entry:
                log_entry[key] = value

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def setup_logging(level: int = logging.INFO) -> None:
    """アプリケーション全体のログ設定を初期化"""
    root = logging.getLogger()
    root.setLevel(level)

    # OTel が注入したハンドラを保護しつつ既存ハンドラを差し替え
    otel_handlers = [
        h for h in root.handlers
        if type(h).__module__.startswith("opentelemetry")
    ]
    root.handlers.clear()
    for h in otel_handlers:
        root.addHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # boto3/botocore のログを抑制
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
