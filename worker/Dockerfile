# worker/Dockerfile

FROM python:3.12.12-slim-bookworm

LABEL maintainer="Foxerine"
LABEL description="A self-contained, secure, stateful Python code interpreter WORKER."

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        supervisor tini fontconfig curl iptables \
        # OpenCV dependencies
        libgl1-mesa-glx libglib2.0-0 \
        # pyzbar dependencies
        libzbar0 \
        # python-magic dependencies
        libmagic1 \
        # FFmpeg and multimedia dependencies
        ffmpeg libavcodec-extra \
        libsm6 libxext6 libxrender1 \
        # Audio processing dependencies (librosa, soundfile)
        libsndfile1 \
        # CairoSVG dependencies
        libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0 \
        # ImageMagick (for wand)
        imagemagick libmagickwand-dev \
        # RAW image processing (rawpy)
        libraw-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home -d /sandbox --shell /bin/bash sandbox && \
    chown -R sandbox:sandbox /sandbox

# Install font
COPY ./assets/simhei.ttf /usr/share/fonts/truetype/
RUN fc-cache -fv

# Install uv
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# Install Python dependencies
WORKDIR /worker
ENV PYTHONPATH=/
COPY ./requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN ipython kernel install --name "python3" --user

# Copy application code & configs
COPY . /worker
COPY ./supervisor/supervisord.conf /etc/supervisor/supervisord.conf

COPY ./entrypoint.sh /worker/entrypoint.sh
RUN chmod +x /worker/entrypoint.sh

# [更新] 将最终的工作目录切换到沙箱
WORKDIR /sandbox

EXPOSE 8000
ENTRYPOINT ["/worker/entrypoint.sh"]

