#!/usr/bin/env sh

set -eu

usage() {
  echo "Usage: $0 [-d] [-f <pipflags>] <venv> <package name>..."
  exit 1
}

install_package() {
  req="$1/requirements.txt"
  dev_req="$1/dev-requirements.txt"

  set -x

  if [ -f "$req" ]; then
    # shellcheck disable=SC2086
    pip install ${flags:-} -r "$req"
  fi

  if [ "${dev:-0}" -eq 1 ] && [ -f "$dev_req" ]; then
    # shellcheck disable=SC2086
    pip install ${flags:-} -r "$dev_req"
  fi

  # shellcheck disable=SC2086
  pip install ${flags:-} "$1"

  set +x
}

while getopts "df:" arg; do
  case "$arg" in
    d)
      dev=1
      ;;
    f)
      flags="$OPTARG"
      ;;
    *)
      usage
      ;;
  esac
done
shift $((OPTIND-1))

if [ "$#" -lt 2 ]; then
  usage
fi

# Because we generate the requirements files from nixpkgs
# we have to ignore dependency requirements as python
# packages in nixpkgs can use the pythonRelaxDepsHook
# to relax dependency requirements
flags="$flags --no-deps"

venv="$1"
shift 1

# shellcheck disable=SC1091
. "$venv/bin/activate"

for p in "$@"; do
  case "$p" in
    moatt_types|moatt_clients|moatt_server)
      install_package "./tunnel/src/$p"
      ;;
    management)
      install_package "./management"
      ;;
    *)
      usage
      ;;
  esac
done
