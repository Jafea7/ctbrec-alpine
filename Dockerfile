# ctbrec-alpine Dockerfile
#
# https://github.com/jafea7/ctbrec-alpine


FROM alpine:latest AS base

ARG TARGETPLATFORM
ARG S6_OVERLAY_VERSION=3.2.0.2

ARG CTBVER
ENV CTBVER=${CTBVER}
ARG CTBWNK
ENV CTBWNK=${CTBWNK}
ENV HOME=/app

# Copy the rootfs layout including files
COPY rootfs/ /

# Install necessary packages
RUN apk add --update --no-cache \
    tar xz jq ffmpeg curl ttf-dejavu \
    openjdk21-jre-headless \
    tzdata python3 py3-urllib3 py3-requests \
    shadow 7zip && \
    # Get s6-overlay tarballs
    [ "$TARGETPLATFORM" = "linux/arm64" ] && S6_ARCH=aarch64 || S6_ARCH=x86_64 && \
    curl -s -L -o /tmp/s6-overlay-noarch.tar.xz https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz && \
    curl -s -L -o /tmp/s6-overlay-${S6_ARCH}.tar.xz https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_ARCH}.tar.xz && \
    curl -s -L -o /tmp/s6-overlay-symlinks-noarch.tar.xz https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-symlinks-noarch.tar.xz && \
    # Extact s6-overlay tarballs
    tar -C / --strip-components=1 -Jxpf /tmp/s6-overlay-noarch.tar.xz && \
    tar -C / --strip-components=1 -Jxpf /tmp/s6-overlay-${S6_ARCH}.tar.xz && \
    tar -C / --strip-components=1 -Jxpf /tmp/s6-overlay-symlinks-noarch.tar.xz && \
    # Remove tarballs
    rm /tmp/s6-overlay-*.tar.xz && \
    # Check if the 'users' group exists, and if not, create it
    if ! getent group users > /dev/null 2>&1; then addgroup -g 1000 users; fi && \
    # Add use 'ctbrec' to users
    adduser -u 1000 -D -h /app -s /bin/false ctbrec && \
    adduser ctbrec users && \
    # Create config and media to ensure they exist
    mkdir -p /app/config /app/media && \
    # Remove tar xz - N.L.R.
    apk del tar xz

# Container volumes
VOLUME [ "/app/media", "/app/config" ]

# Expose server non-SSL and SSL ports
EXPOSE 8080 8443

# Healthcheck for container health, reads the http port from server.json
HEALTHCHECK --interval=20s --retries=3 --timeout=3s \
        CMD sh -x /app/healthcheck.sh

# Initialise
ENTRYPOINT ["/init"]
