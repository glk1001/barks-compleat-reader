#!/bin/bash

set -u

declare -r THIS_SCRIPT_PATH="$(cd "$(dirname "$0")" >/dev/null 2>&1 ; pwd -P)"

declare -ar IMAGE_FILES=(\
00001 \
00002 \
00003 \
00045 \
00046 \
00047 \
00048 \
00049 \
00050 \
00051 \
00052 \
00053 \
00054 \
00055 \
00056 \
00057 \
00058 \
00059 \
00060 \
00061 \
00062 \
00063 \
00064 \
00210 \
00211 \
)

declare -r ROOT_DIR="/home/greg/Books/Carl Barks/The Golden Christmas Tree/images"

declare i=1
for img_file in ${IMAGE_FILES[@]} ; do
    i_str=$(printf '%02d' ${i})
    convert "${ROOT_DIR}/${img_file}.jpeg" "${ROOT_DIR}/${i_str}.png" 
    i=$((i + 1))
done
