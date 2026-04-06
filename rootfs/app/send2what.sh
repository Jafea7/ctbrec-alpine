#!/bin/sh

# send2what.sh discord|telegram|email ${absolutePath} [${modelName} ${localDateTime(YYYYMMDD-HHmmss)} ...]
# Sends the contact sheet to the requested service.

socmed=$(echo "$1" | tr '[:upper:]' '[:lower:]')
shift
file="$1"
sheet="${file%.*}.jpg"

# Calculate duration
length=$(ffprobe "$file" -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 -sexagesimal | cut -d '.' -f 1 | awk -F: '{ printf "%02d:%02d:%02d\n", $1, $2, $3 }')
shift

# Build caption/content string from remaining arguments
if [ -z "$1" ]; then
    content="Contact sheet"
else
    content="$1"
    shift
    for i in "$@"; do
        content="$content - $i"
    done
fi
content="$content: $length"

case "$socmed" in
  discord)
    curl -s --form 'payload_json={"username": "CTBRec", "content":"'"${content}"'"}' \
          --form "file1=@$sheet" "$DISCORDHOOK" > /dev/null
    ;;
  telegram)
    # Combined command: sends the photo AND the caption in one request
    curl -s -X POST "https://api.telegram.org/bot$TOKEN/sendPhoto" \
          -F "chat_id=$CHAT_ID" \
          -F "photo=@$sheet" \
          -F "caption=$content" > /dev/null 2>&1
    ;;
  email)
    name=$(basename "$sheet")
    encoded=$(base64 "$sheet")
    {
      echo "MIME-Version: 1.0"
      echo "Subject: $content"
      echo "Content-Type: multipart/mixed; boundary=\"Delimiter\""
      echo ""
      echo "--Delimiter"
      echo "Content-Type: image/jpeg; name=\"$name\""
      echo "Content-Disposition: attachment; filename=\"$name\""
      echo "Content-Transfer-Encoding: base64"
      echo ""
      echo "$encoded"
      echo "--Delimiter--"
    } > /app/captures/temp.txt
    
    curl -s --url "$MAILSERVER" --ssl-reqd \
          --mail-from "$MAILFROM" --mail-rcpt "$MAILTO" \
          --upload-file '/app/captures/temp.txt' \
          --user "$MAILFROM:$MAILPASS" > /dev/null
    rm /app/captures/temp.txt
    ;;
esac