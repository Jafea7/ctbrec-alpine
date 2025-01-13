#!/bin/python3

# send2ntfy.py ${absolutePath}
# Sends the contact sheet to a NTFY server plus Pin and Delete actions.

import argparse
import requests
import os
import subprocess
import re

# Get environment variables
ntfy_url = os.environ.get('NTFYURL') # NTFY server URL
ntfy_tkn = os.environ.get('NTFYTKN') # NTFY server authentication token
ntfy_act = os.environ.get('NTFYACT') # NTFY action server (ntfy-mm-ssl.py script) handles Pin/Delete msgs from notification
ntfy_ext = os.environ.get('NTFYEXT') # File extension of contact sheet

parser = argparse.ArgumentParser(prog='send2ntfy', description='send2ntfy: Send contact sheet from CTBRec to NTFY')
parser.add_argument('file', type=str, help='Video file')

args = parser.parse_args()
if (args.file is None):
  parser.error('File required')

video_name = args.file
contact_sheet = os.path.splitext(video_name)[0] + ntfy_ext

# Get video duration using ffmpeg (because it's already there)
process = subprocess.Popen(['/app/ffmpeg/ffmpeg',  '-hide_banner', '-i', video_name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT).communicate()[0].decode('utf-8')
matches = re.search(r"Duration:\s(.+?)\.", process)
description = matches[0]

# Use string formatting to generate authorisation
authorization = f"Bearer {ntfy_tkn}"

# Use string formatting to generate actions
actions_body = f"http, Pin, {ntfy_act}, body='{{\"action\": \"pin\", \"filename\": \"{video_name}\"}}'; http, Delete, {ntfy_act}, body='{{\"action\": \"delete\", \"filename\": \"{video_name}\"}}'"

requests.post(ntfy_url,
  data=open(contact_sheet, 'rb'),
  headers={
    "Authorization": authorization,
    "Title": description,
    "Filename": contact_sheet,
    "Actions": actions_body
  })
