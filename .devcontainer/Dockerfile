FROM mcr.microsoft.com/devcontainers/python:3.12

# uv インストール（公式イメージからコピー）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# キャッシュ効率化
ENV UV_LINK_MODE=copy
