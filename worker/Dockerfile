# worker/Dockerfile

FROM python:3.12-slim-bookworm

LABEL maintainer="Foxerine"
LABEL description="A self-contained, secure, stateful Python code interpreter WORKER."

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1

# [新增] 创建沙箱目录，这将是代码执行的默认工作区
RUN mkdir /sandbox

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends supervisor tini fontconfig libgl1-mesa-glx libglib2.0-0 curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install font
COPY ./assets/simhei.ttf /usr/share/fonts/truetype/
RUN fc-cache -fv

# Install Python dependencies
WORKDIR /worker
# [更新] 将 PYTHONPATH 设置为 /worker，以便在 /sandbox 中也能导入应用代码
ENV PYTHONPATH=/worker
COPY ./requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN ipython kernel install --name "python3" --user

# Copy application code & configs
COPY . /worker
COPY ./supervisor/supervisord.conf /etc/supervisor/supervisord.conf

# [更新] 将最终的工作目录切换到沙箱
WORKDIR /sandbox

EXPOSE 8000
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/bin/supervisord", "-c", "/etc/supervisor/supervisord.conf"]
