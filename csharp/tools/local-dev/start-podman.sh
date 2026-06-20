#!/usr/bin/env bash
# Podman-flavoured variant of start-docker.sh.
#
# Why a separate script: the Docker version uses `docker build`, whose BuildKit
# "container" driver does NOT load the resulting image into Podman's image store
# (the build only lands in the build cache), so the subsequent `compose up
# --no-build` can't find {project-name}-api/{project-name}-ui. Podman also can't run the x86
# mssql/server image and, in a shared Podman VM, SQL Server can be OOM-killed.
#
# This script therefore:
#   - builds with `podman build` (loads into Podman, supports --secret)
#   - points `docker compose` at the Podman machine socket (DOCKER_HOST)
#   - writes a runtime override: Azure SQL Edge (ARM) + a SQL Server memory cap
#     + restart policies, and moves the API HTTP port off 5000 if it's taken
#     (e.g. by macOS AirPlay Receiver).
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CSHARP_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
NUGET_CONFIG="$CSHARP_DIR/nuget.config"
FRONTEND_DOCKERFILE="$SCRIPT_DIR/Dockerfile.{project-name}-ui"
BACKEND_DOCKERFILE="$CSHARP_DIR/src/backend/{ClientName}.{ProjectName}.API/Dockerfile"
CERT_PASSWORD="${PROJECT_NAME_API_CERTIFICATE_PASSWORD:-local-dev-cert-pass}"
CERT_DIR="$HOME/.aspnet/https"
CERT_PATH="$CERT_DIR/aspnetapp.pfx"
IMAGE_PREFIX="localhost/"
SQL_MEMORY_LIMIT_MB="${MSSQL_MEMORY_LIMIT_MB:-4096}"
TEMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t {project-name}-local-dev)"

cleanup() { rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

log() { printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }
die() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
require_command() { command -v "$1" >/dev/null 2>&1 || die "Required command '$1' was not found."; }

detect_host() {
  local kernel machine
  kernel="$(uname -s)"
  machine="$(uname -m)"
  HOST_OS="unknown"
  APPLE_SILICON="false"
  case "$kernel" in
    Darwin*) HOST_OS="macos" ;;
    MINGW*|MSYS*|CYGWIN*) HOST_OS="windows" ;;
    Linux*)
      if grep -qi microsoft /proc/version 2>/dev/null; then HOST_OS="wsl"; else HOST_OS="linux"; fi ;;
  esac
  if [ "$HOST_OS" = "macos" ] && [ "$machine" = "arm64" ]; then APPLE_SILICON="true"; fi
}

read_nuget_config_value() {
  local key="$1"
  sed -nE "s/.*<add[[:space:]]+key=\"$key\"[[:space:]]+value=\"([^\"]+)\".*/\1/p" "$NUGET_CONFIG" | head -n 1
}

resolve_config_value() {
  local value="$1"
  if [[ "$value" =~ ^%([A-Za-z_][A-Za-z0-9_]*)%$ ]]; then
    local variable_name="${BASH_REMATCH[1]}"
    printf '%s' "${!variable_name:-}"
    return
  fi
  printf '%s' "$value"
}

resolve_nuget_credentials() {
  [ -f "$NUGET_CONFIG" ] || die "Missing $NUGET_CONFIG."
  local configured_username configured_password
  configured_username="$(read_nuget_config_value "Username")"
  configured_password="$(read_nuget_config_value "ClearTextPassword")"
  NUGET_FEED_USERNAME="${NUGET_FEED_USERNAME:-$(resolve_config_value "$configured_username")}"
  NUGET_FEED_CLEAR_TEXT_PASSWORD="${NUGET_FEED_CLEAR_TEXT_PASSWORD:-${PAT:-$(resolve_config_value "$configured_password")}}"
  if [ -z "${NUGET_FEED_USERNAME:-}" ] || [ "$NUGET_FEED_USERNAME" = "YOUR_USERNAME" ]; then
    die "Export NUGET_FEED_USERNAME (or set it in nuget.config) before running this script."
  fi
  if [ -z "${NUGET_FEED_CLEAR_TEXT_PASSWORD:-}" ] || \
     [ "$NUGET_FEED_CLEAR_TEXT_PASSWORD" = "YOUR_PAT" ] || \
     [ "$NUGET_FEED_CLEAR_TEXT_PASSWORD" = "YOUR_PERSONAL_ACCESS_TOKEN" ]; then
    die "Export PAT (your Azure Artifacts PAT) before running this script."
  fi
  export NUGET_FEED_USERNAME NUGET_FEED_CLEAR_TEXT_PASSWORD
  export PAT="$NUGET_FEED_CLEAR_TEXT_PASSWORD"
}

generate_openssl_cert() {
  require_command openssl
  local openssl_config="$TEMP_DIR/localhost-openssl.cnf"
  cat > "$openssl_config" <<'EOF'
[req]
default_bits = 2048
distinguished_name = dn
prompt = no
x509_extensions = v3_req
[dn]
CN = localhost
[v3_req]
subjectAltName = @alt_names
[alt_names]
DNS.1 = localhost
IP.1 = 127.0.0.1
EOF
  openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 365 \
    -keyout "$CERT_DIR/aspnetapp.key" -out "$CERT_DIR/aspnetapp.crt" \
    -config "$openssl_config" >/dev/null 2>&1
  openssl pkcs12 -export -out "$CERT_PATH" \
    -inkey "$CERT_DIR/aspnetapp.key" -in "$CERT_DIR/aspnetapp.crt" \
    -passout "pass:$CERT_PASSWORD" >/dev/null 2>&1
  [ -f "$CERT_PATH" ] || return 1
  chmod 644 "$CERT_PATH" "$CERT_DIR/aspnetapp.crt" 2>/dev/null || true
}

ensure_https_cert() {
  mkdir -p "$CERT_DIR"
  if [ -f "$CERT_PATH" ]; then
    log "Using existing HTTPS certificate at $CERT_PATH"
    log "  (it must have been created with password '$CERT_PASSWORD'; export PROJECT_NAME_API_CERTIFICATE_PASSWORD if not)"
    return
  fi
  log "Creating local HTTPS certificate (password: $CERT_PASSWORD)"
  generate_openssl_cert || die "Failed to create HTTPS certificate."
}

ensure_podman() {
  require_command podman
  podman machine inspect >/dev/null 2>&1 || die "No Podman machine. Run: podman machine init && podman machine start"
  if ! podman info >/dev/null 2>&1; then
    log "Starting Podman machine"
    podman machine start || die "Could not start the Podman machine."
  fi
  DOCKER_HOST="unix://$(podman machine inspect --format '{{.ConnectionInfo.PodmanSocket.Path}}' 2>/dev/null)"
  export DOCKER_HOST
  log "DOCKER_HOST -> $DOCKER_HOST"
  docker compose version >/dev/null 2>&1 || \
    die "'docker compose' not available. Install docker-compose and add cliPluginsExtraDirs to ~/.docker/config.json."
}

build_images() {
  log "Building backend image ${IMAGE_PREFIX}{project-name}-api (podman build)"
  podman build \
    -f "$BACKEND_DOCKERFILE" \
    --secret id=nuget_username,env=NUGET_FEED_USERNAME \
    --secret id=nuget_password,env=NUGET_FEED_CLEAR_TEXT_PASSWORD \
    -t "${IMAGE_PREFIX}{project-name}-api" \
    "$CSHARP_DIR"

  log "Building frontend image ${IMAGE_PREFIX}{project-name}-ui (podman build)"
  podman build \
    -f "$FRONTEND_DOCKERFILE" \
    --secret id=ado_pat,env=PAT \
    -t "${IMAGE_PREFIX}{project-name}-ui" \
    "$CSHARP_DIR/src/frontend"
}

pick_api_http_port() {
  API_HTTP_PORT=5000
  if lsof -nP -iTCP:5000 -sTCP:LISTEN >/dev/null 2>&1; then
    API_HTTP_PORT=5002
    log "Host port 5000 is in use (often macOS AirPlay Receiver) -> mapping API HTTP to ${API_HTTP_PORT}"
  fi
}

write_podman_override() {
  PODMAN_OVERRIDE="$TEMP_DIR/docker-compose.podman.yml"
  cat > "$PODMAN_OVERRIDE" <<EOF
services:
  mssql:
    image: mcr.microsoft.com/azure-sql-edge:latest
    environment:
      - MSSQL_MEMORY_LIMIT_MB=${SQL_MEMORY_LIMIT_MB}
    restart: unless-stopped
  api:
    ports: !override
      - "${API_HTTP_PORT}:8080"
      - "5001:8081"
    restart: unless-stopped
EOF
}

compose() { docker compose -f "$CSHARP_DIR/docker-compose.yml" -f "$PODMAN_OVERRIDE" "$@"; }

compose_up() {
  export DOCKER_REGISTRY="${IMAGE_PREFIX}"
  export PROJECT_NAME_API_CERTIFICATE_PASSWORD="$CERT_PASSWORD"
  export PROJECT_NAME_DB_CONNECTION_STRING="${PROJECT_NAME_DB_CONNECTION_STRING:-Server=mssql,1433;Database={ProjectName}Db;User Id=sa;Password=Strong_password_123!;TrustServerCertificate=True;MultipleActiveResultSets=true;}"
  log "Removing old {project-name} containers, if any"
  compose down --remove-orphans >/dev/null 2>&1 || true
  log "Starting {project-name} containers on Podman"
  compose up -d --no-build
}

wait_for_api() {
  log "Waiting for API migrations, mock data, and startup"
  local attempt state
  for attempt in $(seq 1 120); do
    if curl -kfsS https://localhost:5001/system/info >/dev/null 2>&1; then return; fi
    state="$(docker inspect -f '{{.State.Status}}' {project-name}_api 2>/dev/null || true)"
    if [ "$state" = "exited" ]; then
      log "API exited before dependencies were ready; restarting it"
      docker start {project-name}_api >/dev/null 2>&1 || true
    fi
    sleep 5
  done
  docker logs --tail 160 {project-name}_api >&2 || true
  die "API did not become reachable at https://localhost:5001/system/info."
}

wait_for_frontend() {
  log "Waiting for frontend"
  local attempt
  for attempt in $(seq 1 60); do
    if curl -fsS -I http://localhost:3000 >/dev/null 2>&1; then return; fi
    sleep 2
  done
  docker logs --tail 120 {project-name}_ui >&2 || true
  die "Frontend did not become reachable at http://localhost:3000."
}

main() {
  require_command curl
  require_command sed
  require_command lsof

  detect_host
  [ "$APPLE_SILICON" = "true" ] || log "Note: Azure SQL Edge is applied for Podman regardless of arch."
  resolve_nuget_credentials
  ensure_https_cert
  ensure_podman
  pick_api_http_port
  write_podman_override
  build_images
  compose_up
  wait_for_api
  wait_for_frontend

  log "{PROJECT-NAME} is running on Podman"
  printf '\nFrontend: %s\n' "http://localhost:3000"
  printf 'API:      %s   (HTTP on :%s)\n' "https://localhost:5001" "$API_HTTP_PORT"
  printf 'Swagger:  %s\n\n' "https://localhost:5001/docs/index.html"
  printf 'Do not commit local secrets or runtime data: csharp/nuget.config, csharp/typesense-data/.\n'
}

main "$@"
