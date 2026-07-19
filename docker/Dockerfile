# Apache Ossie 動作確認用の環境。
# ホストを汚さないよう、検証はすべてこのコンテナ内で完結させる。
FROM python:3.12-slim

# uv はレイヤを薄く保つために公式イメージからコピーする
COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends \
        git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DBT_PROFILES_DIR=/work/track-a/dbt-project

WORKDIR /work

# 依存はビルド時に固定する。実行時にネットワークへ出ないようにするため。
COPY docker/requirements.txt /tmp/requirements.txt
RUN uv venv /opt/venv --python 3.12 \
    && uv pip install --python /opt/venv/bin/python -r /tmp/requirements.txt

CMD ["bash"]
