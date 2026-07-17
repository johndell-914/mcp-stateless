#!/usr/bin/env bash
#
# Rebuild the app image (via Cloud Build) and redeploy a Cloud Run service.
# Image-only update -> preserves the service's IAP gate, VPC egress, ingress,
# env vars, and secrets (they are never re-passed here, so they stick).
#
# Run it from anywhere authenticated to the project — including Cloud Shell,
# which needs no local Docker:
#     git pull
#     bash deploy/redeploy.sh                    # rebuild + redeploy the UI (default)
#     bash deploy/redeploy.sh mcp-stateless-proxy # redeploy a specific service
#
# Config is derived from `gcloud config` and overridable via env vars, so no
# project identifiers are hardcoded (this repo is public):
#     PROJECT   defaults to `gcloud config get-value project`
#     REGION    defaults to us-central1
#     REPO      Artifact Registry repo name, defaults to mcp-stateless
#
set -euo pipefail

PROJECT="${PROJECT:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-mcp-stateless}"
SERVICE="${1:-mcp-stateless-ui}"

if [ -z "${PROJECT}" ]; then
  echo "No project set. Run: gcloud config set project <your-project-id>" >&2
  exit 1
fi

IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/${REPO}/app:latest"

echo "Project=${PROJECT}  Region=${REGION}  Service=${SERVICE}"
echo "-> Building image: ${IMAGE}"
gcloud builds submit --tag "${IMAGE}" . --quiet

echo "-> Redeploying ${SERVICE} (image-only; IAP / VPC / env / secrets preserved)"
gcloud run deploy "${SERVICE}" --image "${IMAGE}" --region "${REGION}" --quiet

URL="$(gcloud run services describe "${SERVICE}" --region "${REGION}" \
        --format='value(status.url)' 2>/dev/null || true)"
echo "Done.${URL:+  URL: ${URL}}"
