#!/bin/sh
# append.sh ${absoluteParentPath} otime
#
# Where: otime = time in minutes, files younger than this will be concatenated
#
# e.g. append.sh ${absoluteParentPath} 60
#      Concat files whose modification time is less than 60 minutes old

# Exit Codes:
# 0 - Successful or less than 2 files
# 1 - Time period less than or equal to 0
# 2 - Resolution of files do not match
# 3 - Contenation unsuccessful

path=$1
otime=$2

# Check $otime is not <=0
if [ "$otime" -le 0 ]; then
  exit 1
fi

# Find and sort files between otime and ntime minutes old
files=$(find "$path" -type f -mmin -$otime -print | xargs stat -c '%Y %n' | sort -n | cut -d' ' -f2-)

# Check if files list is empty, if yes exit
if [ -z "$files" ]; then
  exit 0
fi

# Get the number of files, if <2 exit
count=$(echo "$files" | wc -l)
if [ "$count" -lt 2 ]; then
  exit 0
fi

# Get the latest file (last in the sorted list), its timestamp, and resolution
earliest=$(echo "$files" | head -n 1)
timestamp=$(date -d @$(stat -c %Y "$earliest") "+%y%m%d%H%M.%S")
resolution=$(/app/ffprobe -v error -select_streams v -show_entries stream=width,height -of csv=p=0:s=x "$earliest")

# Remove the previous list if it exists
rm -f "/app/infiles.txt"

# Write file paths to /app/infiles.txt
for file in $files; do
  tempres=$(/app/ffprobe -v error -select_streams v -show_entries stream=width,height -of csv=p=0:s=x "$file")
# If a files resolution does not match the initial file, exit
  if [ $tempres != $resolution ]; then
    exit 2
  fi
  echo "file $file" >> /app/infiles.txt
done

# Append files to temp output
ffmpeg -hide_banner -v quiet -xerror -f concat -safe 0 -i /app/infiles.txt -c copy "$path/tempconcat.mkv"

# If successful, remove original files and rename temp to earliest
if [ $? -eq 0 ]; then
  for file in $files; do
    rm "$file"
  done
  mv "$path/tempconcat.mkv" "$earliest"
  touch -t "$timestamp" "$earliest"
else
  rm -f "$path/tempconcat.mkv"
  exit 3
fi
