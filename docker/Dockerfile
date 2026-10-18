# FE Maker build image: GBA toolchain for the fireemblem8u decomp.
# Contains no Nintendo data. The ROM is mounted read-only at run time.
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        binutils-arm-none-eabi \
        gcc-arm-none-eabi \
        git \
        ca-certificates \
        pkg-config \
        libpng-dev \
        python3 \
        python3-numpy \
        python3-pil \
        rsync \
    && rm -rf /var/lib/apt/lists/*

# agbcc (pret/agbcc), pinned for reproducible builds.
ARG AGBCC_COMMIT=da598c1d918402c42c0c0d7128ba14567f3175e9
RUN git clone https://github.com/pret/agbcc.git /tmp/agbcc \
    && cd /tmp/agbcc \
    && git checkout "$AGBCC_COMMIT" \
    && ./build.sh \
    && mkdir -p /opt/agbcc-project \
    && ./install.sh /opt/agbcc-project \
    && mv /opt/agbcc-project/tools/agbcc /opt/agbcc \
    && rm -rf /tmp/agbcc /opt/agbcc-project

COPY entrypoint.sh /usr/local/bin/fe-maker-build
RUN chmod +x /usr/local/bin/fe-maker-build

# /src  : decomp sources (read-only, the untouched submodule)
# /rom  : user's ROM as /rom/baserom.gba (read-only)
# /work : working copy of the decomp (named volume, keeps build cache)
# /out  : build outputs
ENTRYPOINT ["fe-maker-build"]
