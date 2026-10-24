#!/bin/bash
# Runs in the fe-maker-cskillsys image (prototype, ticket 27).
#   /src         C-SkillSys tree with its Tools (FE-CLib-Mokha, EventAssembler, FE-PyTools), read-only
#   /in/rom.gba  the ROM to patch (our build, or the original game)
#   /in/vanilla.elf, /in/vanilla.gba, /in/ours.elf: the original game built from the decomp and
#                our build (no port when absent)
#   /out         fe8-kernel.gba and the build log
# /work (a volume) keeps the Event Assembler tools between runs.
set -euo pipefail

mkdir -p /work/ea
if [ ! -x /work/ea/ColorzCore ]; then
    echo "[cskillsys] Building Event Assembler tools..."
    rsync -a /src/Tools/EventAssembler/ /work/ea/
    (cd /work/ea && bash build.sh) > /out/ea-build.log 2>&1 || { tail -40 /out/ea-build.log; exit 1; }
fi

echo "[cskillsys] Copying the sources..."
rm -rf /work/tree
rsync -a --exclude Tools/EventAssembler /src/ /work/tree/
ln -s /work/ea /work/tree/Tools/EventAssembler
cd /work/tree
# gcc 15 (devkitARM) does not pass -I to the assembler for .s files: give it the include folders
sed -i 's|^CFLAGS += -std=gnu99$|CFLAGS += -std=gnu99 $(foreach dir, $(INC_DIRS), -Wa,-I,$(dir))|' makefile
grep -q -- "-Wa,-I" makefile

if [ -f /in/ours.elf ]; then
    echo "[cskillsys] Moving addresses to this build..."
    python3 /opt/port.py /in/vanilla.elf /in/ours.elf /work/tree /in/vanilla.gba > /out/port.log
    tail -1 /out/port.log | grep -E "addresses moved" || true
    grep -c "^\[conflict\]" /out/port.log || true
fi
(cd Tools/FE-CLib-Mokha && make -f template.mk reference/fireemblem8.ref.o)

cp /in/rom.gba fe8.gba
echo "[cskillsys] Building C-SkillSys..."
make -j"$(nproc)" CONFIG_EA_WIN=0 > /out/make.log 2>&1 || { tail -60 /out/make.log; exit 1; }
cp fe8-kernel-dev.gba /out/fe8-kernel.gba
[ -f fe8-kernel-dev.sym ] && cp fe8-kernel-dev.sym /out/ || true
echo "[cskillsys] Done"
