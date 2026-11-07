# Read after the decomp's Makefile for a native Windows build (make -f Makefile -f win.mk FEM_NATIVE=<this folder>).
# Only recipes that cannot run as written on Windows are replaced; the decomp itself is never modified.

# The decomp echoes ~1900 object names on one command line, past Windows' 32 KB limit: make writes the list itself.
$(OBJECTS_LST): $(ALL_OBJECTS)
	$(file >$@,$(ALL_OBJECTS))

# tools/jsonproc has no license, so it is not shipped: same output from a Python script of FE Maker.
JSONPROC := $(PYTHON) $(FEM_NATIVE)/jsonproc.py

FETSATOOL := $(PYTHON) scripts/gfxtools/tsa_generator.py
TMAP2TSA := $(PYTHON) scripts/tmap2tsa.py
MARTOMAP := $(PYTHON) scripts/mar_to_map.py

%.fk: % ; $(PYTHON) scripts/compressor.py $< fk

# Battle animations: same output as scripts/arm_compressing_linker.py, in seconds instead of 10+ minutes
# (banim_link.py says why). Scripts are run through $(PYTHON): Windows does not run a file by its #! line.
$(BANIM_OBJECT): $(shell $(PYTHON) $(FEM_NATIVE)/banim_link.py -m -o x -t linker_script_banim.txt -b 0 -l x --objcopy x --gbagfx x)
	$(PYTHON) $(FEM_NATIVE)/banim_link.py -o $@ -t linker_script_banim.txt -b 0x8c02000 -l $(LD) --objcopy $(OBJCOPY) --gbagfx $(GBAGFX)
