#!/bin/sh

# publish.sh - Build and push Docker images to GitHub Container Registry
set -e

REGISTRY="ghcr.io/foxerine"
GATEWAY_IMAGE="$REGISTRY/code-interpreter-gateway"
WORKER_IMAGE="$REGISTRY/code-interpreter-worker"

# Default tag: git short hash
TAG=$(git rev-parse --short HEAD)
PUSH_LATEST=true

# --- Parse arguments ---
while [ "$#" -gt 0 ]; do
  case "$1" in
    --tag) TAG="$2"; shift 2;;
    --no-latest) PUSH_LATEST=false; shift;;
    -h|--help)
      echo "Usage: $0 [OPTIONS]"
      echo "Options:"
      echo "  --tag <string>    Image tag (default: git short hash)"
      echo "  --no-latest       Don't also tag as 'latest'"
      echo "  -h, --help        Show this help message"
      echo ""
      echo "Prerequisites:"
      echo "  echo \$GHCR_TOKEN | docker login ghcr.io -u USERNAME --password-stdin"
      exit 0
      ;;
    *) echo "Unknown parameter: $1"; exit 1;;
  esac
done

echo "📦 Publishing images to $REGISTRY"
echo "   Tag: $TAG"
echo "   Push latest: $PUSH_LATEST"
echo ""

# --- Build images ---
echo "🔨 [1/3] Building gateway image..."
docker build -t "$GATEWAY_IMAGE:$TAG" ./gateway

echo ""
echo "🔨 [2/3] Building worker image..."
docker build -t "$WORKER_IMAGE:$TAG" ./worker

# --- Tag latest ---
if [ "$PUSH_LATEST" = "true" ]; then
    docker tag "$GATEWAY_IMAGE:$TAG" "$GATEWAY_IMAGE:latest"
    docker tag "$WORKER_IMAGE:$TAG" "$WORKER_IMAGE:latest"
fi

# --- Push images ---
echo ""
echo "🚀 [3/3] Pushing images to registry..."
docker push "$GATEWAY_IMAGE:$TAG"
docker push "$WORKER_IMAGE:$TAG"

if [ "$PUSH_LATEST" = "true" ]; then
    docker push "$GATEWAY_IMAGE:latest"
    docker push "$WORKER_IMAGE:latest"
fi

echo ""
echo "✅ Published successfully!"
echo "   $GATEWAY_IMAGE:$TAG"
echo "   $WORKER_IMAGE:$TAG"
if [ "$PUSH_LATEST" = "true" ]; then
    echo "   $GATEWAY_IMAGE:latest"
    echo "   $WORKER_IMAGE:latest"
fi
echo ""
echo "To use these images:"
echo "   ./start.sh                        # uses latest"
echo "   ./start.sh --image-tag $TAG       # uses specific version"
