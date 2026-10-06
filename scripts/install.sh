#!/usr/bin/env bash
# HakiAI installer for Linux (x86_64, glibc 2.35 or newer), D34. Installs the packaged release for the current user;
# HakiAI itself needs no root. Typical use:
#   curl -fsSL https://raw.githubusercontent.com/raykl640/ICS-PROJECT/main/scripts/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/raykl640/ICS-PROJECT/main/scripts/install.sh | bash -s -- --uninstall
# Options: --version vX.Y.Z   a specific release instead of the latest
#          --no-ollama        do not offer to install Ollama (the local AI engine)
#          --no-setup         do not download the AI models now (HakiAI does it on its first start)
#          --uninstall        remove HakiAI; asks before deleting accounts and history (--purge: delete without asking)
# Env:     HAKI_REPO (owner/name on GitHub), HAKI_TARBALL (install this local file instead of downloading; a
#          "<file>.sha256" next to it is checked when present).
set -euo pipefail

REPO="${HAKI_REPO:-raykl640/ICS-PROJECT}"
ASSET="HakiAI-linux-x86_64.tar.gz"
MIN_GLIBC="2.35"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_DIR="$DATA_HOME/hakiai-app"
BIN_LINK="$HOME/.local/bin/hakiai"
DESKTOP_FILE="$DATA_HOME/applications/hakiai.desktop"
ICON_FILE="$DATA_HOME/icons/hicolor/256x256/apps/hakiai.png"
USER_DATA="$DATA_HOME/HakiAI"
OLLAMA_SCRIPT="https://ollama.com/install.sh"

VERSION="latest"
WANT_OLLAMA=1
WANT_SETUP=1
ACTION="install"
PURGE=0

say() { printf '%s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

usage() {
  say "Install HakiAI for the current user:  install.sh [--version vX.Y.Z] [--no-ollama] [--no-setup]"
  say "Remove it:                            install.sh --uninstall [--purge]"
}

# ask "question" → 0 for yes. Reads the terminal even when this script is piped into bash; no terminal → no.
ask() {
  local answer
  (: </dev/tty) 2>/dev/null || return 1
  printf '%s [Y/n] ' "$1" >/dev/tty
  read -r answer </dev/tty || return 1
  case "$answer" in [nN]*) return 1 ;; *) return 0 ;; esac
}

fetch() {
  if command -v curl >/dev/null; then
    curl -fL --progress-bar -o "$2" "$1"
  elif command -v wget >/dev/null; then
    wget -q --show-progress -O "$2" "$1"
  else
    die "curl or wget is needed to download HakiAI"
  fi
}

check_platform() {
  [ "$(uname -s)" = "Linux" ] || die "this installer is for Linux; on Windows use the .exe from the releases page"
  [ "$(uname -m)" = "x86_64" ] || die "HakiAI is built for x86_64 only (this machine: $(uname -m))"
  local glibc
  glibc="$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}')" || true
  [ -n "$glibc" ] || die "HakiAI needs glibc $MIN_GLIBC or newer (musl-based systems such as Alpine are not supported)"
  [ "$(printf '%s\n%s\n' "$MIN_GLIBC" "$glibc" | sort -V | head -n1)" = "$MIN_GLIBC" ] ||
    die "HakiAI needs glibc $MIN_GLIBC or newer (this system: $glibc); run it from source instead (see the README)"
}

release_url() {
  if [ "$VERSION" = "latest" ]; then
    echo "https://github.com/$REPO/releases/latest/download/$1"
  else
    echo "https://github.com/$REPO/releases/download/$VERSION/$1"
  fi
}

# get_tarball DIR → path of the verified tarball inside DIR.
get_tarball() {
  local dir="$1" tarball="$1/$ASSET"
  if [ -n "${HAKI_TARBALL:-}" ]; then
    [ -f "$HAKI_TARBALL" ] || die "HAKI_TARBALL=$HAKI_TARBALL does not exist"
    cp "$HAKI_TARBALL" "$tarball"
    [ ! -f "$HAKI_TARBALL.sha256" ] || cp "$HAKI_TARBALL.sha256" "$tarball.sha256"
  else
    say "Downloading HakiAI ($VERSION) from github.com/$REPO ..." >&2
    fetch "$(release_url "$ASSET")" "$tarball" || die "download failed; check the internet connection and the release"
    fetch "$(release_url "$ASSET.sha256")" "$tarball.sha256" >/dev/null 2>&1 ||
      die "the release has no $ASSET.sha256, so the download cannot be verified"
  fi
  if [ -f "$tarball.sha256" ]; then
    (cd "$dir" && sha256sum --check --status "$ASSET.sha256") || die "checksum mismatch: the download is damaged"
  fi
  echo "$tarball"
}

write_desktop_entry() {
  mkdir -p "$(dirname "$DESKTOP_FILE")" "$(dirname "$ICON_FILE")"
  cp "$APP_DIR/hakiai.png" "$ICON_FILE"
  cat >"$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=HakiAI
GenericName=Legal information assistant
Comment=Kenyan law in plain language, offline
Exec="$APP_DIR/HakiAI"
Icon=$ICON_FILE
Terminal=true
Categories=Education;Office;
EOF
  command -v update-desktop-database >/dev/null && update-desktop-database -q "$(dirname "$DESKTOP_FILE")" || true
}

offer_ollama() {
  command -v ollama >/dev/null && return 0
  [ "$WANT_OLLAMA" -eq 1 ] || return 0
  say ""
  say "HakiAI writes its answers with Ollama, a local AI engine, which is not installed."
  if ask "Install Ollama now with its official installer ($OLLAMA_SCRIPT)? It asks for your password."; then
    fetch "$OLLAMA_SCRIPT" "$TMP/ollama-install.sh" && sh "$TMP/ollama-install.sh" ||
      say "Ollama was not installed; install it later from https://ollama.com/download"
  else
    say "Skipped. Install it later from https://ollama.com/download (laws can be read and searched without it)."
  fi
}

offer_setup() {
  [ "$WANT_SETUP" -eq 1 ] || return 0
  say ""
  if ask "Download the AI models now (about 5 GB; otherwise HakiAI does it on its first start)?"; then
    "$APP_DIR/HakiAI" --setup || say "The download did not finish; HakiAI retries on its first start."
  fi
}

install_app() {
  check_platform
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  local tarball staging="$APP_DIR.new"
  tarball="$(get_tarball "$TMP")"
  rm -rf "$staging"
  mkdir -p "$staging"
  tar -xzf "$tarball" -C "$staging" --strip-components=1
  [ -x "$staging/HakiAI" ] || die "the archive does not contain HakiAI/HakiAI"
  rm -rf "$APP_DIR"
  mv "$staging" "$APP_DIR"
  mkdir -p "$(dirname "$BIN_LINK")"
  ln -sfn "$APP_DIR/HakiAI" "$BIN_LINK"
  write_desktop_entry
  say "HakiAI is installed in $APP_DIR"
  offer_ollama
  offer_setup
  say ""
  say "Start HakiAI from your applications menu, or run: hakiai"
  case ":$PATH:" in
    *":$(dirname "$BIN_LINK"):"*) ;;
    *) say "(~/.local/bin is not on your PATH; add it, or run $BIN_LINK)" ;;
  esac
}

uninstall_app() {
  rm -rf "$APP_DIR" "$APP_DIR.new" "$DESKTOP_FILE" "$ICON_FILE"
  [ ! -L "$BIN_LINK" ] || rm -f "$BIN_LINK"
  say "HakiAI is removed."
  if [ -d "$USER_DATA" ]; then
    if [ "$PURGE" -eq 1 ] || ask "Also delete your HakiAI accounts and saved history in $USER_DATA?"; then
      rm -rf "$USER_DATA"
      say "Deleted $USER_DATA"
    else
      say "Kept your accounts and history in $USER_DATA"
    fi
  fi
  say "Ollama and the downloaded models were left in place (remove them with 'ollama rm' and ~/.cache/huggingface)."
}

while [ $# -gt 0 ]; do
  case "$1" in
    --version) [ $# -ge 2 ] || die "--version needs a value, e.g. v2.0.0"; VERSION="$2"; shift ;;
    --no-ollama) WANT_OLLAMA=0 ;;
    --no-setup) WANT_SETUP=0 ;;
    --uninstall) ACTION="uninstall" ;;
    --purge) PURGE=1 ;;
    -h | --help) usage; exit 0 ;;
    *) die "unknown option $1 (see --help)" ;;
  esac
  shift
done

if [ "$ACTION" = "uninstall" ]; then uninstall_app; else install_app; fi
