# worker/Dockerfile

FROM python:3.12.12-slim-bookworm

LABEL maintainer="Foxerine"
LABEL description="A self-contained, secure, stateful Python/Node.js code interpreter WORKER."

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1

# =============================================================================
# System Dependencies Installation
# TODO: [OPTIMIZATION] Consider splitting into base/full images for lighter deployments
# =============================================================================

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

# =============================================================================
# Document Processing Dependencies (Skills Support)
# TODO: [OPTIMIZATION] LibreOffice is ~500MB, consider lazy loading or separate image
# =============================================================================

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # LibreOffice for document conversion (docx, xlsx, pptx, pdf)
        libreoffice-writer libreoffice-calc libreoffice-impress \
        libreoffice-common fonts-liberation \
        # Pandoc for markdown/document conversion
        pandoc \
        # PDF processing tools
        poppler-utils qpdf \
        # OCR support (optional but useful for scanned PDFs)
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim \
        # Ghostscript for PDF enhancement
        ghostscript \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# =============================================================================
# Node.js Runtime (Skills Support)
# TODO: [OPTIMIZATION] Consider using Node.js Alpine variant or lazy loading
# =============================================================================

# Install Node.js 18 LTS
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install global npm packages for document processing
# TODO: [OPTIMIZATION] Consider installing these on-demand or in a separate layer
RUN npm install -g \
        docx \
        pptxgenjs \
        typescript \
        ts-node \
    && npm cache clean --force

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

# =============================================================================
# Playwright Browser Installation (Skills Support)
# TODO: [OPTIMIZATION] Playwright + Chromium adds ~400MB, consider lazy loading
# TODO: [SECURITY] Review browser sandbox settings for production
# =============================================================================

# Install Playwright browsers (Chromium only to save space)
RUN playwright install chromium && \
    playwright install-deps chromium

# Copy application code & configs
COPY . /worker
COPY ./supervisor/supervisord.conf /etc/supervisor/supervisord.conf

COPY ./entrypoint.sh /worker/entrypoint.sh
RUN chmod +x /worker/entrypoint.sh

# [更新] 将最终的工作目录切换到沙箱
WORKDIR /sandbox

EXPOSE 8000
ENTRYPOINT ["/worker/entrypoint.sh"]

