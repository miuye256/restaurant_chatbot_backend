FROM python:3.11-slim

WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update && \
    apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

# Poetryをインストール
RUN curl -sSL https://install.python-poetry.org | python3 -

# PATHにPoetryを追加
ENV PATH="/root/.local/bin:$PATH"

# Poetry の仮想環境をコンテナ内に作成
RUN poetry config virtualenvs.create false

# 依存関係ファイルをコピー
COPY pyproject.toml poetry.lock* ./

# 依存関係をインストール
RUN poetry install --no-root

# アプリケーションのソースコードをコピー
COPY . .

EXPOSE 8000

CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 