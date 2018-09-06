#!/bin/bash

set -o errexit
#set -x

cd "$(dirname $0)"
BIN_DIR="${PWD}"
PROG_DIR="${BIN_DIR%/*}"
TOP_DIR="${PROG_DIR%/*}"

cd ${TOP_DIR}/env
source ./bin/activate

# note: we need to sudo because of this:
#       screen.py: Must run as root to be able to access /dev/mem
cd ${PROG_DIR} && sudo ./main.py

exit 0
