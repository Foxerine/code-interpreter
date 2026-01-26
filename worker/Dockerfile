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
        supervisor tini fontconfig curl iptables git \
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
        sharp \
        react \
        react-dom \
        react-icons \
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

# =============================================================================
# Skills Repository (Claude Code Skills)
# Copy from git submodule for latest skill definitions
# Path: /mnt/skills/{skill-name}/...
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
    # Ensure skills are readable by sandbox user (read-only)
    chmod -R a+rX /mnt/skills

# Install canvas-design fonts to system
RUN cp /mnt/skills/canvas-design/canvas-fonts/*.ttf /usr/share/fonts/truetype/ && \
    fc-cache -fv

# =============================================================================
# Frontend Libraries (Offline versions for isolated sandbox)
# =============================================================================
RUN mkdir -p /mnt/libs && \
    curl -fsSL https://cdnjs.cloudflare.com/ajax/libs/p5.js/1.11.3/p5.min.js -o /mnt/libs/p5.min.js && \
    curl -fsSL https://fonts.gstatic.com/s/poppins/v22/pxiEyp8kv8JHgFVrJJfecg.woff2 -o /usr/share/fonts/truetype/Poppins-Regular.woff2

COPY ./entrypoint.sh /worker/entrypoint.sh
RUN chmod +x /worker/entrypoint.sh

# [更新] 将最终的工作目录切换到沙箱
WORKDIR /sandbox

EXPOSE 8000
ENTRYPOINT ["/worker/entrypoint.sh"]

