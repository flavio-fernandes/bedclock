#!/bin/bash
set -o errexit
set -x

cd "$(dirname $0)"
BIN_DIR="${PWD}"
PROG_DIR="${BIN_DIR%/*}"
TOP_DIR="${PROG_DIR%/*}"

pushd ${TOP_DIR}
if [ ! -e ./env ]; then
    ##time python3 -m venv env
    time python3 -m venv --system-site-packages env
fi
source ./env/bin/activate
##pip3 install --ignore-installed --verbose -r ./requirements.txt
#sudo pip3 install --ignore-installed -r ./requirements.txt
pip3 install -r ./requirements.txt
deactivate

popd
exit 0
