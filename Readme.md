# CTBRec server Docker image based on Alpine + s6-overlay

---

CTBRec is a streaming media recorder.

---

## Table of Content

   * [Docker container for CTBRec server](#docker-container-for-ctbrec-server)
      * [Table of Content](#table-of-content)
      * [Differences to CTBRec-Debian](#differences-to-ctbrec-debian)
      * [Quick Start](#quick-start)
      * [Usage](#usage)
         * [Environment Variables](#environment-variables)
         * [Data Volumes](#data-volumes)
         * [Ports](#ports)
         * [Changing Parameters of a Running Container](#changing-parameters-of-a-running-container)
      * [Docker Compose File](#docker-compose-file)
      * [QNap Installs](#qnap-installs)
      * [Docker Image Update](#docker-image-update)
         * [Synology](#synology)
         * [unRAID](#unraid)
      * [Accessing the GUI](#accessing-the-gui)
      * [Shell Access](#shell-access)
      * [Default Web Interface Access](#default-web-interface-access)
      * [Extras](#extras)
         * [Ancillary Scripts](#ancillary-scripts)
         * [Send2 Scripts](#send2-scripts)


## Differences to CTBRec-Debian

- CTBRec is run via the s6 supervisor, the container will generally stop faster and cleaner, (if CTBRec was idle), instead of Docker force closing at 10 seconds.

  If you use `docker stop --time=610 CONTAINER` then this is basically waiting for CTBRec to force close it's processes before exiting.
- The use of PUID/PGID seems to work correctly.
- **The directory where the recordings are saved has CHANGED to `/app/media`, map it accordingly.**
- `send2discord.sh`, `send2email.sh`, and `send2telegram.sh` have been combined into one script, `send2what.sh`.
- `send2http.sh` has not been tested.
- The `healthcheck.sh` reads the httpPort value from the server.json file, so if you need to change it due to a clash the healthcheck will still work.
- The contact sheet is now 3840px wide and consists of 10x9 images, (timecode burn-in working again - thanks @Tactic).

**NOTE:** Do not just drop your old config in and expect it to work, you'll be ignored.


## Quick Start

**NOTE**: The Docker command provided in this quick start is given as an **example** and parameters should be adjusted to your need.

Launch the CTBRec server docker container with the following command:
```
docker run -d \
    --name=ctbrec-alpine \
    -p 18080:8080 \
    -p 18443:8443 \
    -v /where/ever/media:/app/media:rw \
    -v /where/ever/.config/ctbrec:/app/config:rw \
    -e TZ=Australia/Sydney \
    -e PGID=1001 \
    -e PUID=1001 \
    jafea7/ctbrec-alpine
```

Where:
  - `/where/ever/.config/ctbrec`: This is where the application stores its configuration and any files needing persistency.
  - `/where/ever/media`:          This is where the application stores recordings.
  - `TZ`:                          The timezone you want the application to use, files created will be referenced to this.
  - `PGID`:                        The Group ID that CTBRec will run under.
  - `PUID`:                        The User ID that CTBRec will run under.

Browse to `http://your-host-ip:18080` to access the CTBRec web interface, (or `https://your-host-ip:18443` if TLS is enabled).

**NOTE**: If it's your initial use of this image then a default config is copied that already has the web interface enabled along with TLS.

## Usage

```
docker run [-d] \
    --name=ctbrec-alpine \
    [-e <VARIABLE_NAME>=<VALUE>]... \
    [-v <HOST_DIR>:<CONTAINER_DIR>[:PERMISSIONS]]... \
    [-p <HOST_PORT>:<CONTAINER_PORT>]... \
    jafea7/ctbrec-alpine
```
| Parameter | Description |
|-----------|-------------|
| -d        | Run the container in the background.  If not set, the container runs in the foreground. |
| -e        | Pass an environment variable to the container.  See the [Environment Variables](#environment-variables) section for more details. |
| -v        | Set a volume mapping (allows to share a folder/file between the host and the container).  See the [Data Volumes](#data-volumes) section for more details. |
| -p        | Set a network port mapping (exposes an internal container port to the host).  See the [Ports](#ports) section for more details. |

### Environment Variables

To customize some properties of the container, the following environment
variables can be passed via the `-e` parameter (one for each variable).  Value
of this parameter has the format `<VARIABLE_NAME>=<VALUE>`.

| Variable       | Description                                  | Default |
|----------------|----------------------------------------------|---------|
|`TZ`| [TimeZone] of the container.  Timezone can also be set by mapping `/etc/localtime` between the host and the container. | `UTC` |
|`PGID`| Group ID that will be used to run CTBRec within the container. | `1000` |
|`PUID`| User ID that will be used to run CTBRec within the container. | `1000` |
|`WINK`| Use WinkRU server, set to `true` if required. | `false` |

### Data Volumes

The following table describes data volumes used by the container.  The mappings
are set via the `-v` parameter.  Each mapping is specified with the following
format: `<HOST_DIR>:<CONTAINER_DIR>[:PERMISSIONS]`.

| Container path  | Permissions | Description |
|-----------------|-------------|-------------|
|`/app/config`| rw | This is where the application stores its configuration and any files needing persistency. |
|`/app/media`| rw | This is where the application stores recordings. |

### Ports

Here is the list of ports used by the container.  They can be mapped to the host
via the `-p` parameter (one per port mapping).  Each mapping is defined in the
following format: `<HOST_PORT>:<CONTAINER_PORT>`.  The port number inside the
container cannot be changed, but you are free to use any port on the host side.

| Port | Mapping to host | Description |
|------|-----------------|-------------|
| 8080 | Mandatory | Port used to serve HTTP requests. |
| 8443 | Mandatory | Port used to serve HTTPs requests. |

### Changing Parameters of a Running Container

As seen, environment variables, volume mappings and port mappings are specified
while creating the container.

The following steps describe the method used to add, remove or update
parameter(s) of an existing container.  The generic idea is to destroy and
re-create the container:

  1. Stop the container (if it is running):
```
docker stop ctbrec-alpine
```
  2. Remove the container:
```
docker rm ctbrec-alpine
```
  3. Create/start the container using the `docker run` command, by adjusting
     parameters as needed.

**NOTE**: Since all application's data is saved under the mapped `/app/config` and
`/app/media` folders, destroying and re-creating a container is not a problem:
nothing is lost and the application comes back with the same state (as long as
the mapping of the `/app/config` and `/app/media` folders remain the same).

## Docker Compose File

Here is an example of a `docker-compose.yml` file that can be used with
[Docker Compose](https://docs.docker.com/compose/overview/).

Make sure to adjust according to your needs.  Note that only mandatory network
ports are part of the example.

```yaml
services:
  ctbrec-alpine:
    image: jafea7/ctbrec-alpine
    container_name: "ctbrec-alpine"
    environment:
      - TZ=Australia/Sydney
      - PGID=1001
      - PUID=1001
    ports:
      - "18080:8080"
      - "18443:8443"
    volumes:
      - "/where/ever/.config/ctbrec:/app/config:rw"
      - "/where/ever/media:/app/media:rw"
    restart: "unless-stopped"
```

## QNap Installs

When you create the container using Container Station specify the PUID and PGID environment variables, (you can't do this later).

You may need to set `PGID = 0` and `PUID = 0`, ie. CTBRec runs as root within the container.

## Docker Image Update

If the system on which the container runs doesn't provide a way to easily update
the Docker image, the following steps can be followed:

  1. Fetch the latest image:
```
docker pull jafea7/ctbrec-alpine
```
  2. Stop the container:
```
docker stop jafea7/ctbrec-alpine
```
  3. Remove the container:
```
docker rm jafea7/ctbrec-alpine
```
  4. Start the container using the `docker run` command.


**Updating using docker-compose:**
```
docker-compose pull && docker-compose up -d
```

### Synology

For owners of a Synology NAS, the following steps can be used to update a
container image.

  1.  Open the *Docker* application.
  2.  Click on *Registry* in the left pane.
  3.  In the search bar, type the name of the container (`jafea7/ctbrec-alpine`).
  4.  Select the image, click *Download* and then choose the `latest` tag.
  5.  Wait for the download to complete.  A  notification will appear once done.
  6.  Click on *Container* in the left pane.
  7.  Select your CTBRec server container.
  8.  Stop it by clicking *Action*->*Stop*.
  9.  Clear the container by clicking *Action*->*Clear*.  This removes the
      container while keeping its configuration.
  10. Start the container again by clicking *Action*->*Start*.
  
  **NOTE**:  The container may temporarily disappear from the list while it is re-created.
---

### unRAID

For unRAID, a container image can be updated by following these steps:

  1. Select the *Docker* tab.
  2. Click the *Check for Updates* button at the bottom of the page.
  3. Click the *update ready* link of the container to be updated.

## Accessing the GUI

Assuming that container's ports are mapped to the same host's ports, the
interface of the application can be accessed with a web browser at:

```
http://<HOST IP ADDR>:8080
```
Or if TLS is enabled:

```
https://<HOST IP ADDR>:8443
```

## Shell Access

To get shell access to the running container, execute the following command:

```
docker exec -ti CONTAINER sh
```

**NOTE:** The internal shell is Ash, that's it, there are no Bash niceties.

Where `CONTAINER` is the ID or the name of the container used during its
creation (e.g. `ctbrec-alpine`).

## Default Web Interface Access

After a fresh install and the web interface is enabled, the default login is:
  - Username: `ctbrec`
  - Password: `sucks`

Change the username/password via the WebUI, you will need to log into it again after saving.

**NOTE**: A fresh start of the image will include a current default server.json, (if it doesn't exist already), with the following options set:
  - `"deleteOrphanedRecordingMetadata": true`
  - `"disabledSites" : [ "SecretFriends", "LiveJasmin", "MV Live", "Amateur.tv", "CherryTV" ]`
  - `"downloadFilename": "$sanitize(${modelName})_$sanitize(${siteName})_$format(${localDateTime},yyyyMMdd-hhmmss).${fileSuffix}"`
  - `"recordingsDirStructure": "ONE_PER_MODEL"`
  - `"totalModelCountInTitle": true`
  - `"transportLayerSecurity": true`
  - `"webinterface": true`

These post-processing steps will be set in the default config:
  - Run external script `dopp.sh` to check the existence of the flag file to enable or disable post-processing, (see [Ancillary Scripts](#ancillary-scripts));
  - Run external script `plcheck.sh` which checks the `playlist.m3u8` generated by CTBRec is terminated correctly, (see [Ancillary Scripts](#ancillary-scripts));
  - Remux/Transcode to a matroska container;
  - Rename to the following: `"$sanitize(${modelName})_$sanitize(${siteName})_$format(${localDateTime},yyyyMMdd-hhmmss).${fileSuffix}"`;
  - Create contact sheet: 10x9 images, 3840px wide, same file name format as the Rename step.


## Extras

### Ancillary Scripts

**dopp.sh**

This script controls post-processing by checking the existence of a `flag` file.

Why does this script exist?

In case you're running the server on low powered hardware, (or some other reason), it gives you a way to defer post-processing to a time of your choosing without having to:
- stop the server;
- remove post-processing steps;
- start the server;
- wait for all your recordings to finish;
- stop the server;
- add the post-processing steps back;
- start the server;
- and finally `Re-run post-processing` from the client.

If the file `dopp` exists in the mapped `/app/config` directory then post-processing will continue as normal.

If the file does not exist then post-processing will be aborted and the recording marked as `FAILED` in the interface.

To run post-processing on the recording, create the dopp file and `Re-run post-processing` either via the button in the WebUI or the context menu in the client.

The relevant entry for post-processing is:
```
    {
      "type": "ctbrec.recorder.postprocessing.Script",
      "config": {
        "script.params": "",
        "script.executable": "/app/dopp.sh"
      }
    }
```

**NOTE:** By default this script is the **first step** in post-processing and the `dopp` file will be created whenever the container is started so that post-processing works as normal.

---

**plcheck.sh**

A simple script that will check if `playlist.m3u8` is terminated correctly, only useful if you don't record as a single file.

If the container is terminated without existing captures being finished correctly the `playlist.m3u8` file won't be terminated with `#EXT-X-ENDLIST` which will cause ffmpeg to truncate the recording and take excessive time to process.

By default this step happens before any following remux, (obviously), in post-processing, if `playlist.m3u8` doesn't exist, (in the case of `Record Single File` being enabled), or is correctly terminated it will exit otherwise it will append `#EXT-X-ENDLIST` to the file which will allow post-processing to be re-run without causing problems.

The relevant entry for post-processing is:
```json
    {
      "type": "ctbrec.recorder.postprocessing.Script",
      "config": {
        "script.params": "${absolutePath}",
        "script.executable": "/app/plcheck.sh"
      }
    }
```

---

**append.sh**

**NOTE:** __Do not use this script if all captures go to a single directory!__

Shell script that appends video segments within a time period into one file.

It has two parameters: `${absoluteParentPath}` and `time`

| Parameter | Description |
|-----------|-------------|
| `${absoluteParentPath}` | Passed from CTBRec as the directory for each broadcasters captures |
| `time` | Time in minutes for files within a period, uses file modification date |

This script should be followed by the `RemoveKeepFiles` post-processing step since the capture records will be incorrect.

If post-processing fails on this step there are exit codes which identify what went wrong, look in the container log and check below:

| Exit Code | Meaning |
|-----------|---------|
| 0 | Normal exit or less than two files |
| 1 | Invalid parameters |
| 2 | Video dimensions not equal |
| 3 | Concatenation failed |

The relevant entry for post-processing is:
```json
    {
      "type": "ctbrec.recorder.postprocessing.Script",
      "config": {
        "script.params": "${absoluteParentPath} time",
        "script.executable": "/app/append.sh"
      }
    }
```

**NOTE:** The original files will be deleted if the append operation was successful.

**ALSO NOTE:** Do not use this with the `mash.sh` script.

---

**mash.sh**

**NOTE: DO NOT USE THIS SCRIPT UNLESS YOU HAVE READ THE FOLLOWING AND KNOW EXACTLY WHAT IT WILL MEAN.**

This script adds files to an encrypted archive where the password is based on a SHA256 hash of the original file name, the resultant file will have an MP4 extension.

It is recommended that the file name end in the date/time in ISO8601 format, i.e. `some_name_20240912-125634.mkv`, because the final file name will be `20240912-125634.mp4`.

The script takes two parameters, the first is the full path to the file, i.e. `${absolutePath}`, the second is optional and can be anything, if it is present the original file will be deleted after encryption.

Using the above example file name, `some_name_20240912-125634.mkv`, a SHA256 hash will be calculated, (`1ca2462e6d1fd3f802774b268531c3def8c5e822b2ece592decfea0cf4b2659a`), and used in the following way:

`7z a -p"1ca2462e6d1fd3f802774b268531c3def8c5e822b2ece592decfea0cf4b2659a" -mhe=on -mx=0 20240912-125634.mp4 some_name_20240912-125634.mkv`

The output file will then just appear to be a corrupt MP4.

Once you've downloaded the files you can extract the files by `7z x -p"1ca2462e6d1fd3f802774b268531c3def8c5e822b2ece592decfea0cf4b2659a" 20240912-125634.mp4`

If you're wondering where the password is stored, it isn't - since you know what the initial name was, (because you're the person who set up the Rename function in Post-processing), you can get it by feeding it into a SHA256 generator, e.g.

Linux:   `echo -n some_name_20240912-125634.mkv | sha256sum | cut -d ' ' -f 1`

Windows: `-join ([security.cryptography.sha256managed]::new().ComputeHash([Text.Encoding]::Utf8.GetBytes("some_name_20240912-125634.mkv")).ForEach{$_.ToString("X2")}).ToLower()`

With a lot of files you can easily automate this.

The relevant entry for post-processing is:
```json
    {
      "type": "ctbrec.recorder.postprocessing.Script",
      "config": {
        "script.params": "${absolutePath} [d]",
        "script.executable": "/app/mash.sh"
      }
    }
```

---

**NOTE: The following Python scripts use the server API Python script that was created by *Scooter* and require three environment variables to be able to run.**

You can specify them in a `docker run` command, `docker-compose.yml`, or `.env` file.

The defaults are:
| Variable | Required | Meaning |
|----------|----------|---------|
| SRVURL | Mandatory | URL of the WebUI, default is `https://127.0.0.1:8443` |
| SRVUSR | Mandatory | WebUI username, default is `ctbrec` |
| SRVPSS | Mandatory | WebUI password, default is `sucks` |

Examples:

```text
docker run -d \
    --name=ctbrec-alpine \
    -p 8080:8080 \
    -p 8443:8443 \
    -v /home/ctbrec/media:/app/media:rw \
    -v /home/ctbrec/.config/ctbrec:/app/config:rw \
    -e TZ=Australia/Sydney \
    -e PGID=1000 \
    -e PUID=1000 \
    -e SRVURL=https://127.0.0.1:8443
    -e SRVUSR=ctbrec
    -e SRVPSS=sucks
    jafea7/ctbrec-alpine
```

```yaml
version: '2.1'
services:
  ctbrec-alpine:
    image: jafea7/ctbrec-alpine
    container_name: "ctbrec-alpine"
    environment:
      - TZ=Australia/Sydney
      - PGID=1000
      - PUID=1000
      - SRVURL=https://127.0.0.1:8443
      - SRVUSR=ctbrec
      - SRVPSS=sucks
    ports:
      - "8080:8080"
      - "8443:8443"
    volumes:
      - "/home/ctbrec/.config/ctbrec:/app/config:rw"
      - "/home/ctbrec/media:/app/media:rw"
    restart: "unless-stopped"
```

---

#### reclean.py

Automatically removes orphaned JSON files from the `<config>/recordings` directory left there by the removal of the media file.

This step should be the last in post-processing and the factors required for a JSON file to be removed are:

* the media file does not exist;
* the status of the recording was `FINISHED`.

The relevant entry for post-processing is:

```json
    {
      "type": "ctbrec.recorder.postprocessing.Script",
      "config": {
        "script.params": "",
        "script.executable": "/app/reclean.py"
      }
    }
```

---

#### reclaim.py

`reclaim.py` recovers drive space by **automatically deleting the oldest non-pinned captures** until the required amount of drive space is free.

Besides the above three environment variables it requires one more to specify the minimum amount of space to recover, it can be specified in `docker run` command, `docker-compose.yml`, or `.env` file.

| Variable | Required | Description |
-----------|----------|-------------|
| RECOVER | Mandatory | Specifies the minimum amount of space to recover in bytes |

**NOTE:** **Do NOT** set the value so that the resultant required free space is larger than the available drive space.

This script should be used by adding to the `Events & Actions` section of the settings.

For example:

```json
  "eventHandlers": [
    {
      "actions": [
        {
          "configuration": {
            "file": "/app/reclaim.py"
          },
          "name": "execute reclaim.py",
          "type": "ctbrec.event.ExecuteProgram"
        }
      ],
      "event": "NO_SPACE_LEFT",
      "id": "5a1beebb-32dd-43cd-9848-b894121374fe",
      "name": "Delete oldest video",
      "predicates": [
        {
          "configuration": {},
          "name": "no space left",
          "type": "ctbrec.event.MatchAllPredicate"
        }
      ]
    }
  ],
 ```

### Send2 Scripts

Included are two scripts that will send a contact sheet created by post-processing to a designated Discord, Telegram channel, email address, or POST to HTTP site.

The scripts are called `send2what.sh`, and `send2http.sh` respectively, they reside in the `/app` directory, they are designed to be called after creation of the contact sheet, (no point calling them before a contact sheet is created).

The relevant entries for post-processing are, for example:

```json
    {
      "type": "ctbrec.recorder.postprocessing.Script",
      "enable": true,
      "config": {
        "script.params": "discord ${absolutePath} ${modelDisplayName} $format(${localDateTime},yyyyMMdd-hhmmss)}",
        "script.executable": "/app/send2what.sh"
      }
    }
```

```json
    {
      "type": "ctbrec.recorder.postprocessing.Script",
      "enable": true,
      "config": {
        "script.params": "telegram ${absolutePath} ${modelDisplayName} $sanitize(${siteName}) $format(${localDateTime},yyyyMMdd-hhmmss)}",
        "script.executable": "/app/send2what.sh"
      }
    }
```

```json
    {
      "type": "ctbrec.recorder.postprocessing.Script",
      "enable": true,
      "config": {
        "script.params": "email ${absolutePath} ${modelDisplayName} $sanitize(${siteName}) $format(${localDateTime},yyyyMMdd-hhmmss)}",
        "script.executable": "/app/send2what.sh"
      }
    }
```

```json
    {
      "type": "ctbrec.recorder.postprocessing.Script",
      "enable": true,
      "config": {
        "script.params": "${absolutePath} ${modelDisplayName} $sanitize(${siteName}) $format(${localDateTime},yyyyMMdd-hhmmss)}",
        "script.executable": "/app/send2http.sh"
      }
    }
```

The first variable needs to be `${absolutePath}`, (needed to determine the contact sheet path/name), the following arguments can be anything and any number, (within reason), they will be concatenated with ` - ` and used as the subject.

The duration of the video will be concatenated at the end as `: hh:mm:ss`.

To designate the Discord channel it is to be sent to, create an environment variable called `DISCORDHOOK` with the Discord Webhook.

See [here](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks) for how to get it.

For example:

```text
docker run -d \
    --name=ctbrec-alpine \
    -p 8080:8080 \
    -p 8443:8443 \
    -v /home/ctbrec/media:/app/media:rw \
    -v /home/ctbrec/.config/ctbrec:/app/config:rw \
    -e TZ=Australia/Sydney \
    -e PGID=1000 \
    -e PUID=1000 \
    -e DISCORDHOOK=https://discordapp.com/api/webhooks/<channelID>/<token> \
    jafea7/ctbrec-alpine
```

```yaml
services:
  ctbrec-alpine:
    image: jafea7/ctbrec-alpine
    container_name: "ctbrec-alpine"
    environment:
      - TZ=Australia/Sydney
      - PGID=1000
      - PUID=1000
      - DISCORDHOOK=https://discordapp.com/api/webhooks/<channelID>/<token>
    ports:
      - "8080:8080"
      - "8443:8443"
    volumes:
      - "/home/ctbrec/.config/ctbrec:/app/config:rw"
      - "/home/ctbrec/media:/app/media:rw"
    restart: "unless-stopped"
```

To designate the Telegram channel you need to set two environment variables, `CHAT_ID` and `TOKEN`.

See [here](https://www.shellhacks.com/telegram-api-send-message-personal-notification-bot/) on how to get both.

For example:

```text
docker run -d \
    --name=ctbrec-alpine \
    -p 8080:8080 \
    -p 8443:8443 \
    -v /home/ctbrec/media:/app/media:rw \
    -v /home/ctbrec/.config/ctbrec:/app/config:rw \
    -e TZ=Australia/Sydney \
    -e PGID=1000 \
    -e PUID=1000 \
    -e CHAT_ID=<chat_id> \
    -e TOKEN=<bot token> \
    jafea7/ctbrec-alpine
```

```yaml
services:
  ctbrec-alpine:
    image: jafea7/ctbrec-alpine
    container_name: "ctbrec-alpine"
    environment:
      - TZ=Australia/Sydney
      - PGID=1000
      - PUID=1000
      - CHAT_ID=<chat_id>
      - TOKEN=<bot token>
    ports:
      - "8080:8080"
      - "8443:8443"
    volumes:
      - "/home/ctbrec/.config/ctbrec:/app/config:rw"
      - "/home/ctbrec/media:/app/media:rw"
    restart: "unless-stopped"
```

To send to an email address you need to set four environment variables, `MAILSERVER`, `MAILFROM`, `MAILTO`, and `MAILPASS`.

| Variable | Required | Meaning |
|----------|----------|---------|
| MAILSERVER | Mandatory | Address of the mail server in the form: `smtps://smtp.<domain>:<port>` |
| MAILFROM | Mandatory | Email address the emails are sent from. |
| MAILTO | Mandatory | Email address to send the emails to. |
| MAILPASS | Mandatory | Password for email account sending the emails. |

For example:

```text
docker run -d \
    --name=ctbrec-alpine \
    -p 8080:8080 \
    -p 8443:8443 \
    -v /home/ctbrec/media:/app/media:rw \
    -v /home/ctbrec/.config/ctbrec:/app/config:rw \
    -e TZ=Australia/Sydney \
    -e PGID=1000 \
    -e PUID=1000 \
    -e MAILSERVER=smtps://smtp.gmail.com:465 \
    -e MAILFROM=my_really_cool_email@gmail.com \
    -e MAILTO=woohoo_another_capture@gmail.com \
    -e MAILPASS=my_really_super_secret_p4ssw0rd \
    jafea7/ctbrec-alpine
```

```yaml
services:
  ctbrec-alpine:
    image: jafea7/ctbrec-alpine
    container_name: "ctbrec-alpine"
    environment:
      - TZ=Australia/Sydney
      - PGID=1000
      - PUID=1000
      - MAILSERVER=smtps://smtp.gmail.com:465
      - MAILFROM=my_really_cool_email@gmail.com
      - MAILTO=woohoo_another_capture@gmail.com
      - MAILPASS=my_really_super_secret_p4ssw0rd
    ports:
      - "8080:8080"
      - "8443:8443"
    volumes:
      - "/home/ctbrec/.config/ctbrec:/app/config:rw"
      - "/home/ctbrec/media:/app/media:rw"
    restart: "unless-stopped"
```

---

**NOTE: The following was a request by someone to add to the image and was written by them.  I have no way to test it so I don't know if it works or not.**

Send a POST request to an URL with postprocessing parameters.

Data will be sent as `multipart/form-data`.

| Form Field | Description |
|------------|-------------|
| file | relative path of the recording |
| sheet | the contact sheet file |
| duration | recording file length, format: `hh:mm:ss` |
| argv | `script.params` string set in server.json, base64encoded |

You need three environment Variables: `HTTP_URL`, `CURL_ARGS`, and `CURL_GET`.

| Variable | Required | Meaning |
|----------|----------|---------|
| HTTP_URL  | Mandatory | the url will send the http request to |
| CURL_ARGS | Optional | extra CURL arguments |
| CURL_GET  | Optional | Send GET requests instead, no contact sheet |

For example:

```text
docker run -d \
    --name=ctbrec-alpine \
    -p 8080:8080 \
    -p 8443:8443 \
    -v /home/ctbrec/media:/app/media:rw \
    -v /home/ctbrec/.config/ctbrec:/app/config:rw \
    -e TZ=Australia/Sydney \
    -e PGID=1000 \
    -e PUID=1000 \
    -e HTTP_URL=http://some.url.org \
    -e CURL_ARGS=some_args \
    -e CURL_GET=true \
    jafea7/ctbrec-alpine
```

```yaml
services:
  ctbrec-alpine:
    image: jafea7/ctbrec-alpine
    container_name: "ctbrec-alpine"
    environment:
      - TZ=Australia/Sydney
      - PGID=1000
      - PUID=1000
      - HTTP_URL=http://some.url.org
      - CURL_ARGS=some_args
      - CURL_GET=true
    ports:
      - "8080:8080"
      - "8443:8443"
    volumes:
      - "/home/ctbrec/.config/ctbrec:/app/config:rw"
      - "/home/ctbrec/media:/app/media:rw"
    restart: "unless-stopped"
```

For `docker-compose` you can also add the variables to the `.env` file and reference them from within the `docker-compose.yml` file.
