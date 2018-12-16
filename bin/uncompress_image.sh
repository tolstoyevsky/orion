#!/bin/bash

set -e

if [ -z "$1" ]; then
    >&2 echo "image is not specified"
    exit 1
fi

mkdir "/tmp/$1"

cp "${DOMINION_WORKSPACE}/$1.img.gz" "/tmp/$1"

cp "$(echo "$(which docker-qemu.sh)")" "/tmp/$1"

gzip -d "/tmp/$1/$1.img.gz"
