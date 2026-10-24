# FE Maker playtest image: mGBA without any window, driven by FE Maker over stdin/stdout.
# Contains no Nintendo data and no BIOS (mGBA's built-in BIOS is used). The ROM is mounted read-only at run time.
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        ca-certificates \
        curl \
        zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# mGBA 0.10.5 (MPL-2.0), pinned by commit and archive hash. Only the GBA core, as a static library.
ARG MGBA_COMMIT=26b7884bc25a5933960f3cdcd98bac1ae14d42e2
ARG MGBA_SHA256=9475c26e9fa2f4b30c07ab6636e4b0a5b62e4baee2109ede7b2fecc52edae366
RUN curl -fsSL -o /tmp/mgba.tar.gz "https://github.com/mgba-emu/mgba/archive/$MGBA_COMMIT.tar.gz" \
    && echo "$MGBA_SHA256  /tmp/mgba.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/mgba.tar.gz -C /tmp \
    && cmake -S "/tmp/mgba-$MGBA_COMMIT" -B /tmp/mgba-build \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/mgba \
        -DLIBMGBA_ONLY=ON -DM_CORE_GB=OFF -DM_CORE_GBA=ON \
        -DUSE_PNG=OFF -DUSE_ZLIB=ON -DUSE_FFMPEG=OFF -DUSE_LZMA=OFF -DUSE_MINIZIP=OFF -DUSE_LIBZIP=OFF \
        -DUSE_SQLITE3=OFF -DUSE_ELF=OFF -DUSE_LUA=OFF -DENABLE_SCRIPTING=OFF -DUSE_DEBUGGERS=OFF \
        -DUSE_GDB_STUB=OFF -DUSE_EDITLINE=OFF -DUSE_DISCORD_RPC=OFF -DUSE_EPOXY=OFF \
    && cmake --build /tmp/mgba-build -j"$(nproc)" \
    && cmake --install /tmp/mgba-build \
    && rm -rf /tmp/mgba.tar.gz "/tmp/mgba-$MGBA_COMMIT" /tmp/mgba-build

COPY driver.c /tmp/driver.c
RUN gcc -O2 -o /usr/local/bin/fe-maker-playtest /tmp/driver.c -I/opt/mgba/include \
        -L/opt/mgba/lib -L/opt/mgba/lib64 -lmgba -lz -lpthread -lm \
    && rm /tmp/driver.c

# /rom : the ROM to play (read-only)
ENTRYPOINT ["fe-maker-playtest"]
