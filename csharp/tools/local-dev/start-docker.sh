#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CSHARP_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
NUGET_CONFIG="$CSHARP_DIR/nuget.config"
FRONTEND_DOCKERFILE="$SCRIPT_DIR/Dockerfile.{project-name}-ui"
CERT_PASSWORD="${PROJECT_NAME_API_CERTIFICATE_PASSWORD:-local-dev-cert-pass}"
CERT_DIR="$HOME/.aspnet/https"
CERT_PATH="$CERT_DIR/aspnetapp.pfx"
TEMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t {project-name}-local-dev)"

cleanup() {
  rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

log() {
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

die() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Required command '$1' was not found."
}

detect_host() {
  local kernel machine
  kernel="$(uname -s)"
  machine="$(uname -m)"

  HOST_OS="unknown"
  APPLE_SILICON="false"

  case "$kernel" in
    Darwin*)
      HOST_OS="macos"
      ;;
    MINGW*|MSYS*|CYGWIN*)
      HOST_OS="windows"
      ;;
    Linux*)
      if grep -qi microsoft /proc/version 2>/dev/null; then
        HOST_OS="wsl"
      else
        HOST_OS="linux"
      fi
      ;;
  esac

  if [ "$HOST_OS" = "macos" ] && [ "$machine" = "arm64" ]; then
    APPLE_SILICON="true"
  fi
}

detect_compose() {
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD=(docker compose)
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD=(docker-compose)
  else
    die "Neither 'docker compose' nor 'docker-compose' is available."
  fi
}

read_nuget_config_value() {
  local key="$1"

  sed -nE "s/.*<add[[:space:]]+key=\"$key\"[[:space:]]+value=\"([^\"]+)\".*/\1/p" "$NUGET_CONFIG" \
    | head -n 1
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
    die "Export NUGET_FEED_USERNAME before running this script."
  fi

  if [ -z "${NUGET_FEED_CLEAR_TEXT_PASSWORD:-}" ] || \
     [ "$NUGET_FEED_CLEAR_TEXT_PASSWORD" = "YOUR_PAT" ] || \
     [ "$NUGET_FEED_CLEAR_TEXT_PASSWORD" = "YOUR_PERSONAL_ACCESS_TOKEN" ]; then
    die "Export NUGET_FEED_CLEAR_TEXT_PASSWORD with your Azure Artifacts PAT before running this script."
  fi

  export NUGET_FEED_USERNAME
  export NUGET_FEED_CLEAR_TEXT_PASSWORD
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
    -keyout "$CERT_DIR/aspnetapp.key" \
    -out "$CERT_DIR/aspnetapp.crt" \
    -config "$openssl_config" >/dev/null 2>&1

  openssl pkcs12 -export \
    -out "$CERT_PATH" \
    -inkey "$CERT_DIR/aspnetapp.key" \
    -in "$CERT_DIR/aspnetapp.crt" \
    -passout "pass:$CERT_PASSWORD" >/dev/null 2>&1

  [ -f "$CERT_PATH" ] || return 1
  chmod 644 "$CERT_PATH" "$CERT_DIR/aspnetapp.crt" 2>/dev/null || true
}

generate_dotnet_cert() {
  require_command dotnet

  local dotnet_cert_path="$CERT_PATH"
  if [ "$HOST_OS" = "windows" ] && command -v cygpath >/dev/null 2>&1; then
    dotnet_cert_path="$(cygpath -w "$CERT_PATH")"
  fi

  dotnet dev-certs https -ep "$dotnet_cert_path" -p "$CERT_PASSWORD" || return 1
  dotnet dev-certs https --trust || true
  [ -f "$CERT_PATH" ] || return 1
  chmod 644 "$CERT_PATH" 2>/dev/null || true
}

ensure_https_cert() {
  mkdir -p "$CERT_DIR"

  if [ -f "$CERT_PATH" ]; then
    log "Using existing HTTPS certificate at $CERT_PATH"
    return
  fi

  log "Creating local HTTPS certificate"
  if [ "$HOST_OS" = "macos" ]; then
    generate_openssl_cert
  else
    generate_dotnet_cert || generate_openssl_cert
  fi
}

build_images() {
  export DOCKER_BUILDKIT=1
  [ -f "$FRONTEND_DOCKERFILE" ] || die "Missing frontend Dockerfile: $FRONTEND_DOCKERFILE"

  log "Building backend image {project-name}-api"
  docker build \
    -f "$CSHARP_DIR/src/backend/{ClientName}.{ProjectName}.API/Dockerfile" \
    --secret id=nuget_username,env=NUGET_FEED_USERNAME \
    --secret id=nuget_password,env=NUGET_FEED_CLEAR_TEXT_PASSWORD \
    -t {project-name}-api \
    "$CSHARP_DIR"

  log "Building frontend image {project-name}-ui"
  docker build \
    -f "$FRONTEND_DOCKERFILE" \
    --secret id=ado_pat,env=PAT \
    -t {project-name}-ui \
    "$CSHARP_DIR/src/frontend"
}

write_apple_compose_override() {
  APPLE_COMPOSE_OVERRIDE="$TEMP_DIR/docker-compose.apple-silicon.yml"

  cat > "$APPLE_COMPOSE_OVERRIDE" <<'EOF'
services:
  mssql:
    image: mcr.microsoft.com/azure-sql-edge:latest
EOF
}

compose_down() {
  log "Removing old local {PROJECT-NAME} containers, if any"
  (
    cd "$CSHARP_DIR"
    "${COMPOSE_CMD[@]}" "${COMPOSE_FILES[@]}" down --remove-orphans
  ) >/dev/null 2>&1 || true
}

compose_up() {
  export PROJECT_NAME_API_CERTIFICATE_PASSWORD="$CERT_PASSWORD"
  export PROJECT_NAME_DB_CONNECTION_STRING="${PROJECT_NAME_DB_CONNECTION_STRING:-Server=mssql,1433;Database={ProjectName}Db;User Id=sa;Password=Strong_password_123!;TrustServerCertificate=True;MultipleActiveResultSets=true;}"

  COMPOSE_FILES=(-f "$CSHARP_DIR/docker-compose.yml")
  if [ "$APPLE_SILICON" = "true" ]; then
    log "Apple Silicon detected; using Azure SQL Edge for the local database"
    write_apple_compose_override
    COMPOSE_FILES+=(-f "$APPLE_COMPOSE_OVERRIDE")
  fi

  # Local-only Mock mode (set PROJECT_NAME_MOCK=1, e.g. via start-mock-docker.sh): layer the Mock override so
  # the backend boots offline with ASPNETCORE_ENVIRONMENT=Mock. No effect on a normal start.
  if [ "${PROJECT_NAME_MOCK:-}" = "1" ] || [ "${PROJECT_NAME_ENV:-}" = "Mock" ]; then
    log "Mock mode: backend runs offline with ASPNETCORE_ENVIRONMENT=Mock"
    COMPOSE_FILES+=(-f "$CSHARP_DIR/../docker-compose.mock.yml")
  fi

  compose_down

  log "Starting {PROJECT-NAME} containers"
  (
    cd "$CSHARP_DIR"
    "${COMPOSE_CMD[@]}" "${COMPOSE_FILES[@]}" up -d --no-build
  )
}

wait_for_api() {
  log "Waiting for API migrations, mock data, and startup"

  local attempt state
  for attempt in $(seq 1 120); do
    if curl -kfsS https://localhost:5001/system/info >/dev/null 2>&1; then
      return
    fi

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
    if curl -fsS -I http://localhost:3000 >/dev/null 2>&1; then
      return
    fi
    sleep 2
  done

  docker logs --tail 120 {project-name}_ui >&2 || true
  die "Frontend did not become reachable at http://localhost:3000."
}

main() {
  require_command docker
  require_command curl
  require_command sed

  detect_host
  detect_compose
  resolve_nuget_credentials
  ensure_https_cert

  docker info >/dev/null 2>&1 || die "Docker is not running."

  log "Host detected: $HOST_OS / $(uname -m)"

  build_images
  compose_up
  wait_for_api
  wait_for_frontend

  log "{PROJECT-NAME} is running"
  printf '\nFrontend: %s\n' "http://localhost:3000"
  printf 'Swagger:  %s\n\n' "https://localhost:5001/docs/index.html"
  printf 'Do not commit local secrets or runtime data: csharp/nuget.config, csharp/typesense-data/.\n'
}

main "$@"
