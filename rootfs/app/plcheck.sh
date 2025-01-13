#!/bin/sh
# Server non-single file use only, checks playlist.m3u8 is terminated correctly.
# plcheck.sh ${absolutePath}

if [ -d "$1" ] && [ -f "${1%/}/playlist.m3u8" ]; then
    echo "#EXT-X-ENDLIST" >> "${1%/}/playlist.m3u8"
else
    exit 0
fi
