#!/bin/bash

declare -r ASPECT_RATIO=1.51
declare -r HEIGHT=$1

declare -r WIDTH=$(echo "${ASPECT_RATIO}*${HEIGHT}" | bc)

echo "width = ${WIDTH}"

