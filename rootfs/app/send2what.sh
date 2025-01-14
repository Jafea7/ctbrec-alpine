#!/bin/sh

# send2what.sh discord|telegram|email ${absolutePath} [${modelName} ${localDateTime(YYYYMMDD-HHmmss)} ...]
# Sends the contact sheet to the requested service.

socmed="$1"
socmed="$(echo "$socmed" | tr '[:lower:]')"
shift
file="$1"
sheet="${file%.*}.jpg"
length=$(ffprobe "$file" -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 -sexagesimal | cut -d '.' -f 1 | awk -F: '{ printf "%02d:%02d:%02d\n", $1, $2, $3 }')
shift

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
    curl --form 'payload_json={"username": "CTBRec", "content":"'"${content}"'"}' --form "file1=@$sheet" "$DISCORDHOOK"
    ;;
  telegram)
    curl --form "photo=@$sheet" --form "caption=$content" --form-string "chat_id=$CHAT_ID" "https://api.telegram.org/bot$TOKEN/sendPhoto"
    ;;
  email)
    encoded=$( base64 "$sheet" )
    echo -e "MIME-Version: 1.0\nSubject: $content\nContent-Type: multipart/mixed;\n  boundary=\"Delimiter\"\n\n--Delimiter\nContent-Type: image/jpeg;\n  name=$name\nContent-Disposition: attachment;\n  filename=$name\nContent-Transfer-Encoding: base64\n\n$encoded\n--Delimiter--\n" > /app/captures/temp.txt
    curl --url "$MAILSERVER" --ssl-reqd --mail-from "$MAILFROM" --mail-rcpt "$MAILTO" --upload-file '/app/captures/temp.txt' --user "$MAILFROM:$MAILPASS"
    rm /app/captures/temp.txt
    ;;
esac
