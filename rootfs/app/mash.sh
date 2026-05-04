#!/bin/sh
# Encrypts files using 7z and optionally delete the original
# Last section of filename should be date-time in ISO8601 format
# e.g. ....._20241101-123456.ts

f=$1
p="${f%/*}"
fn="${f##*/}"
dt="${fn##*_}"
dt="${dt%.*}"
r=$2

# Generate a unique password based on the file name using sha256sum
password=$(echo -n $fn | sha256sum | cut -d ' ' -f 1)

# Create an encrypted 7z archive with no compression, file name as password
7z a -p"$password" -mhe=on -mx=0 "${p}/${dt}.mp4" "$f"

# Optionally, remove the original file after encryption
if [ -n "$r" ]; then
  rm "$f"
fi
