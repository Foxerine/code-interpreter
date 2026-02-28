# worker/Dockerfile
#
# Multi-stage parallel build: BuildKit runs independent stages concurrently.
# Timeline (approximate):
#   node-builder:    |===== Node.js + pnpm packages =====|
#   python-builder:  |===== Python deps + Playwright =====|
#   asset-fetcher:   |== downloads ==|
#   final:           |========== apt-get ALL ==========|← COPY from above stages →|
#
# Requires: DOCKER_BUILDKIT=1 (default in Docker Desktop / Compose v2)

FROM python:3.12.12-slim-bookworm AS base

LABEL maintainer="Foxerine"
LABEL description="A self-contained, secure, stateful Python/Node.js code interpreter WORKER."

ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1


# =============================================================================
# Parallel Stage 1: Node.js packages (independent, no system deps needed)
# Uses official node image - faster than nodesource script
# =============================================================================
FROM node:18.20.8-slim AS node-builder

RUN npm install -g pnpm@10.30.3
ENV PNPM_HOME=/usr/local/share/pnpm
ENV PATH="$PNPM_HOME:$PATH"

RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    mkdir -p $PNPM_HOME && \
    pnpm install -g \
        docx@9.6.0 \
        pptxgenjs@4.0.1 \
        typescript@5.9.3 \
        ts-node@10.9.2 \
        react@19.2.4 \
        react-dom@19.2.4 \
        react-icons@5.5.0 \
        sharp@0.34.5 && \
    ln -sf $(pnpm root -g) /usr/local/lib/node_modules


# =============================================================================
# Parallel Stage 2: Python dependencies + Playwright browser binary
# Wheels are pre-built, no system headers needed at install time
# =============================================================================
FROM base AS python-builder

COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/
COPY ./requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system -r /tmp/requirements.txt && rm /tmp/requirements.txt

RUN ipython kernel install --name "python3" --user

# Download Playwright Chromium binary (system deps installed in final stage)
RUN playwright install chromium


# =============================================================================
# Parallel Stage 3: Asset downloads (lightweight, independent)
# =============================================================================
FROM debian:bookworm-slim AS asset-fetcher

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates fontconfig && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ./assets/simhei.ttf /usr/share/fonts/truetype/

RUN mkdir -p /mnt/libs && \
    curl -fsSL https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.11.3/p5.min.js -o /mnt/libs/p5.min.js && \
    curl -fsSL https://fonts.gstatic.com/s/poppins/v22/pxiEyp8kv8JHgFVrJJfecg.woff2 -o /usr/share/fonts/truetype/Poppins-Regular.woff2

RUN fc-cache -fv


# =============================================================================
# Final Stage: Merge all parallel stages
# =============================================================================
FROM base

# --- System Dependencies (MERGED into one apt-get call) ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        supervisor tini fontconfig iptables git \
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
        # LibreOffice for document conversion (docx, xlsx, pptx, pdf)
        libreoffice-writer libreoffice-calc libreoffice-impress \
        libreoffice-common fonts-liberation \
        # Java runtime for LibreOffice (required for some features)
        default-jre-headless \
        # Pandoc for markdown/document conversion
        pandoc \
        # PDF processing tools
        poppler-utils qpdf \
        # OCR support (optional but useful for scanned PDFs)
        tesseract-ocr tesseract-ocr-eng tesseract-ocr-chi-sim \
        # Ghostscript for PDF enhancement
        ghostscript \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# --- Copy Node.js from official image + pnpm packages from builder ---
COPY --from=node:18.20.8-slim /usr/local/bin/node /usr/local/bin/
COPY --from=node:18.20.8-slim /usr/local/include/node /usr/local/include/node
COPY --from=node-builder /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node-builder /usr/local/share/pnpm /usr/local/share/pnpm
RUN ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx && \
    ln -sf /usr/local/share/pnpm/bin/pnpm /usr/local/bin/pnpm

ENV NODE_PATH="/usr/local/lib/node_modules"
ENV PNPM_HOME="/usr/local/share/pnpm"
ENV PATH="$PNPM_HOME:$PATH"

# --- Copy Python packages + Playwright browser from builder ---
COPY --from=python-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=python-builder /usr/local/bin /tmp/python-bin/
# Merge bin without overwriting existing files (python, pip, etc. already exist in base)
RUN find /tmp/python-bin -maxdepth 1 -type f | while read f; do \
        name=$(basename "$f"); \
        [ ! -f "/usr/local/bin/$name" ] && cp "$f" /usr/local/bin/; \
    done; \
    rm -rf /tmp/python-bin
COPY --from=python-builder /root/.local /root/.local

# Copy Playwright browser binary + install system deps (fast - just runtime libs)
COPY --from=python-builder /root/.cache/ms-playwright /root/.cache/ms-playwright
RUN playwright install-deps chromium && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# --- Copy assets from fetcher ---
COPY --from=asset-fetcher /mnt/libs /mnt/libs
COPY --from=asset-fetcher /usr/share/fonts/truetype/simhei.ttf /usr/share/fonts/truetype/
COPY --from=asset-fetcher /usr/share/fonts/truetype/Poppins-Regular.woff2 /usr/share/fonts/truetype/

# --- Sandbox user ---
RUN useradd --create-home -d /sandbox --shell /bin/bash sandbox && \
    chown -R sandbox:sandbox /sandbox

# --- Install uv (for runtime use) ---
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# --- Application code ---
WORKDIR /worker
ENV PYTHONPATH=/

COPY . /worker
COPY ./supervisor/supervisord.conf /etc/supervisor/supervisord.conf

# =============================================================================
# Skills Repository (Claude Code Skills)
# =============================================================================
COPY ./skills/skills /mnt/skills

# Verify skills submodule was cloned (not empty)
RUN if [ ! -d /mnt/skills/docx ]; then \
        echo ""; \
        echo "========================================================"; \
        echo "ERROR: skills submodule is empty!"; \
        echo ""; \
        echo "Please clone the repository with --recursive:"; \
        echo "  git clone --recursive <repo-url>"; \
        echo ""; \
        echo "Or initialize submodules for existing clone:"; \
        echo "  git submodule update --init --recursive"; \
        echo "========================================================"; \
        echo ""; \
        exit 1; \
    fi && \
    chmod -R a+rX /mnt/skills

# Install canvas-design fonts to system
RUN cp /mnt/skills/canvas-design/canvas-fonts/*.ttf /usr/share/fonts/truetype/ && \
    fc-cache -fv

COPY ./entrypoint.sh /worker/entrypoint.sh
RUN chmod +x /worker/entrypoint.sh

WORKDIR /sandbox

EXPOSE 8000
ENTRYPOINT ["/worker/entrypoint.sh"]
