#!/bin/sh
# note2txt.sh ${absolutePath} ${modelName} ${siteName} ${modelNotes} [${recordingNotes}|"Misc text"]

txtfile="${1%.*}.txt"
model=$2
site=$3
modnote=$4
recnote=$5

{
    echo "Model: $model  Site: $site"
    echo "Model notes:"
    if [ -n "$modnote" ]; then
        echo "$modnote"
    else
        echo "None"
    fi
    echo "Other notes:"
    if [ -n "$recnote" ]; then
        echo "$recnote"
    else
        echo "None"
    fi
} > "$txtfile"
