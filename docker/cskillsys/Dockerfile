# C-SkillSys build image (prototype, ticket 27): the tools FE8U C-SkillSys needs
# (https://github.com/FireEmblemUniverse/fe8u-cskillsys, MIT), as its CI installs them,
# with ColorzCore built for Linux instead of run through wine.
# Contains no Nintendo data and no C-SkillSys sources (mounted at run time).
FROM devkitpro/devkitarm:20260610

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake re2c ghc cabal-install libghc-vector-dev libghc-juicypixels-dev \
        python3 python3-pip python3-pyelftools python3-pil python3-six pkg-config libpng-dev moreutils perl \
        git ca-certificates curl unzip rsync libicu-dev gawk \
    && rm -rf /var/lib/apt/lists/*

# .NET 6 SDK for ColorzCore (Event Assembler)
RUN curl -sSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
    && bash /tmp/dotnet-install.sh --channel 6.0 --install-dir /opt/dotnet \
    && ln -s /opt/dotnet/dotnet /usr/local/bin/dotnet && rm /tmp/dotnet-install.sh
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1

RUN pip3 install --break-system-packages tmx 2>/dev/null || pip3 install tmx
ENV DEVKITPRO=/opt/devkitpro DEVKITARM=/opt/devkitpro/devkitARM
ENV PATH=/opt/devkitpro/tools/bin:/opt/devkitpro/devkitARM/bin:$PATH
WORKDIR /work
COPY port.py /opt/port.py
COPY build.sh /usr/local/bin/cskillsys-build
RUN chmod +x /usr/local/bin/cskillsys-build
ENTRYPOINT ["cskillsys-build"]
