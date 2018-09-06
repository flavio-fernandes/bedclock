#!/bin/bash
#set -o errexit
#set -x

cd "$(dirname $0)"
BIN_DIR="${PWD}"
PROG_DIR="${BIN_DIR%/*}"
TOP_DIR="${PROG_DIR%/*}"

echo "$0 service is now stopped"

exit 0
