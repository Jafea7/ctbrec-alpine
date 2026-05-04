#!/bin/sh
# unmash.sh [--delete] path prefix
#
# e.g. unmash.sh --delete /home/media/files some_model_Bongacams_

# Parameters
delete=0
path=""
prefix=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --delete)
      delete=1
      ;;
    *)
      if [ -z "$path" ]; then
        path="$1"
      elif [ -z "$prefix" ]; then
        prefix="$1"
      fi
      ;;
  esac
  shift
done

if [ -z "$path" ] || [ -z "$prefix" ]; then
  echo "Usage: $0 [--delete] <path> <prefix>"
  exit 1
fi

# Find *.mp4 files in the directory
find "$path" -type f -name "*.mp4" | while IFS= read -r file; do
  # Get the base name (file name without extension)
  origName="${prefix}$(basename "$file" .mp4).mkv"
    
  # Generate the SHA256 hash of the base name
  passwd=$(echo -n "$origName" | sha256sum | cut -d ' ' -f 1)
    
  # Run the 7zip command with the password
  dir=$(dirname "$file")
  
  if 7z x -y -p"$passwd" "$file" -o"$dir" < /dev/null > /dev/null 2>&1; then
    echo "$(basename "$file"): success"
    if [ "$delete" -eq 1 ]; then
      out_file="$dir/$origName"
      if [ -f "$out_file" ]; then
        in_size=$(stat -c %s "$file")
        out_size=$(stat -c %s "$out_file")
        
        min_size=$(( in_size * 9 / 10 ))
        max_size=$(( in_size * 11 / 10 ))
        
        if [ "$out_size" -ge "$min_size" ] && [ "$out_size" -le "$max_size" ]; then
          rm -f "$file"
        fi
      fi
    fi
  else
    echo "$(basename "$file"): fail"
  fi
done
