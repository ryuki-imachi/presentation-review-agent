FROM mcr.microsoft.com/devcontainers/python:3.12

# uv インストール（公式イメージからコピー）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Yarn の apt リポジトリを削除（GPG キー期限切れで apt-get update が失敗するため）
RUN rm -f /etc/apt/sources.list.d/yarn.list

# キャッシュ効率化
ENV UV_LINK_MODE=copy
