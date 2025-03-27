#!/usr/bin/python3

# Models in Group begin in paused state.

# Monitors one model in a group, when they go offline it resumes all other models in the group.
# When the model comes back online it pauses all other models in the group.

import argparse
import json
import os
from ctbrec import CtbRec

# Get server info from OS ENV variables ... or hard code it
srv_url = os.environ.get('SRVURL') # CTBRec server URL:PORT e.g. http://127.0.0.1:11080
srv_usr = os.environ.get('SRVUSR') # CTBRec server username e.g. ctbrec
srv_pwd = os.environ.get('SRVPWD') # CTBRec server password e.g. sucks

# The following gets passed from CTBRec Events & Actions for Model Offline/Online
# e.g. MODEL_STATUS_CHANGED some_model https://www.camsoda.com/some_model CamSoda ONLINE OFFLINE
print('\n--- PvtParts ---')
parser = argparse.ArgumentParser(prog='NaughtyGrabber', description='PvtParts: Monitors one model in a group')
parser.add_argument('event', type=str, help='ONLINE/OFFLINE')
parser.add_argument('model', type=str, help='Model')
parser.add_argument('url', type=str, help='URL')
parser.add_argument('site', type=str, help='Site')
parser.add_argument('before', type=str, help='Previous state')
parser.add_argument('after', type=str, help='Post state')
args = parser.parse_args()

# Create CtbRec python client instance
ctb = CtbRec(server_url=srv_url, username=srv_usr, password=srv_pwd)
# Get CTBRec Groups
data = ctb.get_model_groups().replace("'", '"')
groups = json.loads(data)

found = False
for key, value in groups.items():
  # Search for the passed Event URL in each Group
  if args.url in value.get("modelUrls", []):
    found = True
    # Get URLs in Group excluding the Event URL
    other_urls = [url for url in value["modelUrls"] if url != url]
    # Pause/Resume all the other URLs in the Group depending on state of monitored model
    for url in other_urls:
      if args.after == 'OFFLINE':
        # Trigger model OFFLINE, resume all others in group
        ctb.update_model(url, {'suspended': False})
      else:
        # Trigger model ONLINE, pause all others in group
        ctb.update_model(url, {'suspended': True})
    break

# No match we just drop out the bottom
