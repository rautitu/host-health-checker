#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR="/opt/host-monitor"
CONFIG_DIR="/etc/host-monitor"
STATE_DIR="/var/lib/host-monitor"
LOG_DIR="/var/log/host-monitor"
INSTALL_APT_DEPS=0
INSTALL_CRON=0
DISCORD_WEBHOOK_URL=""

usage() {
  cat <<'EOF'
Usage: deploy/install.sh [options]

Installs host-health-checker on a Linux host.

Options:
  --install-dir PATH          App install directory (default: /opt/host-monitor)
  --config-dir PATH           Config directory (default: /etc/host-monitor)
  --state-dir PATH            State directory (default: /var/lib/host-monitor)
  --log-dir PATH              Log directory (default: /var/log/host-monitor)
  --discord-webhook-url URL   Write HOST_MONITOR_DISCORD_WEBHOOK to the env file
  --install-apt-deps          Run apt-get install for python3, python3-venv, git
  --install-cron              Install /etc/cron.d/host-monitor for daily 09:00 runs
  -h, --help                  Show this help

Examples:
  sudo deploy/install.sh --install-apt-deps --install-cron --discord-webhook-url 'https://discord.com/api/webhooks/...'
  sudo deploy/install.sh --install-cron
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install-dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --config-dir)
      CONFIG_DIR="$2"
      shift 2
      ;;
    --state-dir)
      STATE_DIR="$2"
      shift 2
      ;;
    --log-dir)
      LOG_DIR="$2"
      shift 2
      ;;
    --discord-webhook-url)
      DISCORD_WEBHOOK_URL="$2"
      shift 2
      ;;
    --install-apt-deps)
      INSTALL_APT_DEPS=1
      shift
      ;;
    --install-cron)
      INSTALL_CRON=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${INSTALL_DIR}/.venv/bin/python"
ENV_FILE="${CONFIG_DIR}/env"
CONFIG_FILE="${CONFIG_DIR}/config.toml"
RUNNER="${INSTALL_DIR}/run-daily.sh"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root, for example: sudo $0 $*" >&2
  exit 1
fi

if [[ "${INSTALL_APT_DEPS}" -eq 1 ]]; then
  apt-get update
  apt-get install -y python3 python3-venv git
fi

command -v python3 >/dev/null 2>&1 || {
  echo "python3 is missing. Install it first, or rerun with --install-apt-deps on Debian/Ubuntu." >&2
  exit 1
}

mkdir -p "${INSTALL_DIR}" "${CONFIG_DIR}" "${STATE_DIR}" "${LOG_DIR}/snapshots"

tar \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='.deps' \
  --exclude='.pytest_cache' \
  --exclude='var' \
  -C "${REPO_ROOT}" \
  -cf - . | tar -C "${INSTALL_DIR}" -xf -

python3 -m venv "${INSTALL_DIR}/.venv"
"${PYTHON_BIN}" -m pip install --upgrade pip
"${PYTHON_BIN}" -m pip install "${INSTALL_DIR}"

if [[ ! -f "${CONFIG_FILE}" ]]; then
  cp "${INSTALL_DIR}/config.example.toml" "${CONFIG_FILE}"
  sed -i \
    -e "s#state_path = \"./var/state.json\"#state_path = \"${STATE_DIR}/state.json\"#" \
    -e "s#snapshot_dir = \"./var/snapshots\"#snapshot_dir = \"${LOG_DIR}/snapshots\"#" \
    "${CONFIG_FILE}"
  echo "Created ${CONFIG_FILE}"
else
  echo "Keeping existing ${CONFIG_FILE}"
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  cat > "${ENV_FILE}" <<EOF
HOST_MONITOR_DISCORD_WEBHOOK=${DISCORD_WEBHOOK_URL}
EOF
  chmod 600 "${ENV_FILE}"
  echo "Created ${ENV_FILE}"
elif [[ -n "${DISCORD_WEBHOOK_URL}" ]]; then
  sed -i "s#^HOST_MONITOR_DISCORD_WEBHOOK=.*#HOST_MONITOR_DISCORD_WEBHOOK=${DISCORD_WEBHOOK_URL}#" "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  echo "Updated ${ENV_FILE}"
else
  echo "Keeping existing ${ENV_FILE}"
fi

cat > "${RUNNER}" <<EOF
#!/usr/bin/env bash
set -euo pipefail

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  . "${ENV_FILE}"
  set +a
fi

exec "${PYTHON_BIN}" -m host_monitor daily --config "${CONFIG_FILE}"
EOF
chmod 755 "${RUNNER}"

if [[ "${INSTALL_CRON}" -eq 1 ]]; then
  cat > /etc/cron.d/host-monitor <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin

0 9 * * * root ${RUNNER} >> ${LOG_DIR}/cron.log 2>&1
EOF
  chmod 644 /etc/cron.d/host-monitor
  echo "Installed /etc/cron.d/host-monitor"
fi

"${PYTHON_BIN}" -m host_monitor config-test --config "${CONFIG_FILE}"

cat <<EOF

Install complete.

Config: ${CONFIG_FILE}
Env:    ${ENV_FILE}
Run:    ${RUNNER}

Next:
  1. Edit ${CONFIG_FILE} if needed.
  2. Put the Discord webhook in ${ENV_FILE} if it is still empty.
  3. Test with: ${RUNNER}
EOF

