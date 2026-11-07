"""Fast stand-in for the decomp's scripts/arm_compressing_linker.py (laqieer), same output.

The original links the battle animation blob one entry at a time: for each of ~1475 entries it relinks the whole
blob (2 MB) and spawns ~7 processes, which takes over 10 minutes on Windows. The result is only a byte blob placed
at the base address plus one label per entry, so this script builds the blob in memory and keeps ld for the one
step that needs it: an object entry compressed after linking (the animation scripts, `motion.o|.data.script>lz`),
which is linked exactly as the original does (previous blob first, earlier labels as absolute symbols), then
dumped and compressed.

Outputs, as the original: <out> (the blob as a symbol-less object) and <out>.sym.o (the labels, for `ld -R`).
Usage: banim_link.py -o OUT -t SCRIPT -b BASE_HEX -l LD --objcopy OBJCOPY --gbagfx GBAGFX
"""

import argparse
import os
import subprocess
import sys
import tempfile


def parse_script(path):
    """(file, section, compression) per line, like parse_linker_script of the original."""
    entries = []
    with open(path) as f:
        for line in f:
            if not line.strip() or line[0] in "#\n":
                continue
            comp = None
            if ">" in line:
                line, comp = line.split(">")
                comp = comp.strip()
            line = line.strip()
            section = ".data"
            if "|" in line:
                line, section = (part.strip() for part in line.split("|"))
            entries.append((line, section, comp))
    return entries


def label_for(path):
    """Symbol the original gives a binary entry (convert_binary_to_object)."""
    parts = os.path.basename(path).split(".")
    return parts[0] if parts[1] == "4bpp" else parts[0] + "_" + parts[1]


def is_binary(path):
    return os.path.splitext(path)[-1] not in (".o", ".obj", ".elf")


def run(program, *args):
    # Windows' CreateProcess does not find a relative path with "/" (tools/gbagfx/gbagfx.exe): make it absolute.
    if "/" in program or "\\" in program:
        program = os.path.abspath(program)
    subprocess.run([program, *args], check=True)


class Linker:
    def __init__(self, args, tmp):
        self.args = args
        self.tmp = tmp
        self.blob = bytearray()
        self.symbols = {}  # label -> address, in link order

    def compress(self, path, comp):
        if comp == "lz":
            run(self.args.gbagfx, path, path + ".lz")
            with open(path + ".lz", "rb") as f:
                return f.read()
        if comp == "fk":
            with open(path, "rb") as f:
                data = f.read()
            return (len(data) + 4 << 8).to_bytes(4, "little") + data
        raise SystemExit(f"unknown compression {comp!r}")

    def blob_object(self):
        """The blob so far as a stripped binary object, like change_outputfile_type."""
        bin_path = os.path.join(self.tmp, "blob.bin")
        obj_path = bin_path + ".o"
        with open(bin_path, "wb") as f:
            f.write(self.blob)
        run(self.args.objcopy, "-I", "binary", "-O", "elf32-littlearm", "-B", "armv4t", "-S", bin_path, obj_path)
        return obj_path

    def symbol_script(self):
        path = os.path.join(self.tmp, "symbols.ld")
        with open(path, "w") as f:
            f.writelines(f"{name} = 0x{addr:X};\n" for name, addr in self.symbols.items())
        return path

    def link_object(self, path, section):
        """Link an object's section after the blob (link_to_output, not merged) and return its bytes."""
        base = f"0x{self.args.base:X}"
        elf = os.path.join(self.tmp, "trial.elf")
        inputs = [self.blob_object()] if self.blob else []
        run(self.args.ld, "--no-warn-mismatch", "-e", base, "-Tdata", base, f"--unique={section}",
            "-o", elf, *inputs, path, self.symbol_script())
        out = os.path.join(self.tmp, os.path.basename(path) + ".bin")
        run(self.args.objcopy, "-O", "binary", "-j", section, elf, out)
        return out

    def add(self, path, section, comp):
        if is_binary(path):
            label = label_for(path)
            if comp:
                data = self.compress(path, comp)
                label = label_for(path + "." + comp)
            else:
                with open(path, "rb") as f:
                    data = f.read()
        else:
            if not comp:
                raise SystemExit(f"{path}: an uncompressed object entry is not supported")
            dumped = self.link_object(path, section)
            data = self.compress(dumped, comp)
            label = label_for(path + ".bin." + comp)
        self.symbols[label] = self.args.base + len(self.blob)
        self.blob += data

    def write(self, out):
        bin_path = os.path.splitext(out)[0] + ".bin"
        with open(bin_path, "wb") as f:
            f.write(self.blob)
        run(self.args.objcopy, "-I", "binary", "-O", "elf32-littlearm", "-B", "armv4t", "-S", bin_path, out)
        base = f"0x{self.args.base:X}"
        elf = os.path.join(self.tmp, "final.elf")
        run(self.args.ld, "--no-warn-mismatch", "-e", base, "-Tdata", base, "-o", elf, out, self.symbol_script())
        run(self.args.objcopy, "--extract-symbol", elf, out + ".sym.o")


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("-t", "--script", required=True)
    parser.add_argument("-b", "--base", required=True, type=lambda s: int(s, 16))
    parser.add_argument("-l", "--ld", required=True)
    parser.add_argument("--objcopy", required=True)
    parser.add_argument("--gbagfx", required=True)
    parser.add_argument("-m", "--dependency", action="store_true")
    args = parser.parse_args(argv)
    entries = parse_script(args.script)
    if args.dependency:
        print(" ".join(entry[0] for entry in entries))
        return
    with tempfile.TemporaryDirectory() as tmp:
        linker = Linker(args, tmp)
        for i, entry in enumerate(entries, 1):
            linker.add(*entry)
            if i % 100 == 0 or i == len(entries):
                print(f"Battle animations: {i}/{len(entries)}", flush=True)
        linker.write(args.output)


if __name__ == "__main__":
    main(sys.argv[1:])
