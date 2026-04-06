#!/bin/sh
# unmash.sh path prefix
#
# e.g. unmash.sh /home/media/files some_model_Bongacams_

# Parameters
path="$1"
prefix="$2"

# Find *.mp4 files in the directory
find "$path" -type f -name "*.mp4" | while read file; do
  # Get the base name (file name without extension)
  origName="${prefix}$(basename "$file" .mp4).mkv"
    
  # Generate the SHA256 hash of the base name
  passwd=$(echo -n "$origName" | sha256sum | cut -d ' ' -f 1)
    
  # Run the 7zip command with the password
  dir=$(dirname "$file")
  7z x -p"$passwd" "$file" -o"$dir"
done
