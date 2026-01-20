FROM python:3.12.12-slim-bookworm

RUN apt-get update && \
    apt-get install -y --no-install-recommends e2fsprogs util-linux git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

LABEL maintainer="Foxerine"
LABEL description="Gateway and manager for the Python code interpreter."

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

WORKDIR /gateway
COPY ./requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r /tmp/requirements.txt && rm /tmp/requirements.txt

COPY . /gateway

# --- 新增 ---
# 复制启动脚本并给予执行权限
COPY ./start_gateway.sh /gateway/start_gateway.sh
RUN chmod +x /gateway/start_gateway.sh

EXPOSE 3874

# --- 修改 ---
# 将CMD修改为ENTRYPOINT，以运行我们的启动脚本
ENTRYPOINT ["/gateway/start_gateway.sh"]
