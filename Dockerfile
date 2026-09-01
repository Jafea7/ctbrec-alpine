# ctbrec-alpine Dockerfile
#
# https://github.com/jafea7/ctbrec-alpine


FROM alpine:latest AS base

ARG TARGETPLATFORM
ARG S6_OVERLAY_VERSION=3.2.0.2

ARG CTBVER
ENV CTBVER=${CTBVER}
ENV HOME=/app

# Force VA-API to use the Intel Media driver (ignored on ARM)
# ENV LIBVA_DRIVER_NAME=iHD

# Copy the rootfs layout including files
COPY rootfs/ /

# Install necessary packages
RUN apk add --update --no-cache \
    tar xz jq ffmpeg curl ttf-dejavu \
    openjdk21-jre-headless \
    tzdata python3 py3-urllib3 py3-requests \
    shadow 7zip && \
    # Determine architecture for s6-overlay and driver setup
    if [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
        S6_ARCH="aarch64"; \
    else \
        S6_ARCH="x86_64"; \
        # Install Intel VA-API dependencies from community repo on AMD64
#        apk add --no-cache \
#            --repository=http://dl-cdn.alpinelinux.org/alpine/edge/community/ \
#            libva libva-glx intel-media-driver libva-utils mesa-va-gallium linux-firmware-amdgpu; \
    fi && \
    # Get s6-overlay tarballs
    curl -s -L -o /tmp/s6-overlay-noarch.tar.xz https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz && \
    curl -s -L -o /tmp/s6-overlay-${S6_ARCH}.tar.xz https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_ARCH}.tar.xz && \
    curl -s -L -o /tmp/s6-overlay-symlinks-noarch.tar.xz https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-symlinks-noarch.tar.xz && \
    # Extract s6-overlay tarballs
    tar -C / --strip-components=1 -Jxpf /tmp/s6-overlay-noarch.tar.xz && \
    tar -C / --strip-components=1 -Jxpf /tmp/s6-overlay-${S6_ARCH}.tar.xz && \
    tar -C / --strip-components=1 -Jxpf /tmp/s6-overlay-symlinks-noarch.tar.xz && \
    # Remove tarballs
    rm /tmp/s6-overlay-*.tar.xz && \
    # Check if the 'users' group exists, and if not, create it
    if ! getent group users > /dev/null 2>&1; then addgroup -g 1000 users; fi && \
    # Add user 'ctbrec' to users
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