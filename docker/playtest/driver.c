// Headless mGBA driver for FE Maker playtests.
// Loads a ROM without any window, sound or save file, then answers one command per line on stdin:
//   frames N [MASK]     run N frames holding the key mask (bit 0 = A ... bit 9 = L)  -> "ok"
//   read W ADDR         read an 8/16/32-bit value at a bus address                    -> "ok VALUE"
//   write W ADDR VALUE  write an 8/16/32-bit value                                    -> "ok"
//   screen              current frame, 240 x 160 RGBX                                 -> "ok SIZE" + raw bytes
//   quit
// Numbers may be decimal or 0x-prefixed. Errors answer "error MESSAGE".
#include <mgba/flags.h>
#include <mgba/core/core.h>
#include <mgba/core/log.h>

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void quiet(struct mLogger* logger, int category, enum mLogLevel level, const char* format, va_list args) {
	(void) logger; (void) category; (void) level; (void) format; (void) args;
}

static struct mLogger logger = { .log = quiet };

int main(int argc, char** argv) {
	if (argc != 2) {
		fprintf(stderr, "usage: fe-maker-playtest ROM\n");
		return 1;
	}
	mLogSetDefaultLogger(&logger);
	struct mCore* core = mCoreFind(argv[1]);
	if (!core || !core->init(core)) {
		printf("error cannot open ROM\n");
		return 1;
	}
	mCoreInitConfig(core, NULL);
	unsigned width, height;
	core->desiredVideoDimensions(core, &width, &height);
	color_t* video = calloc((size_t) width * height, sizeof(color_t));
	core->setVideoBuffer(core, video, width);
	if (!mCoreLoadFile(core, argv[1])) {
		printf("error cannot load ROM\n");
		return 1;
	}
	core->reset(core);
	printf("ready %u %u\n", width, height);
	fflush(stdout);

	char line[256];
	while (fgets(line, sizeof(line), stdin)) {
		char command[16] = "";
		uint32_t a = 0, b = 0, c = 0;
		int count = sscanf(line, "%15s %" SCNi32 " %" SCNi32 " %" SCNi32, command, &a, &b, &c);
		if (count < 1) {
			continue;
		}
		if (!strcmp(command, "frames") && count >= 2) {
			core->setKeys(core, count >= 3 ? b : 0);
			for (uint32_t i = 0; i < a; ++i) {
				core->runFrame(core);
			}
			printf("ok\n");
		} else if (!strcmp(command, "read") && count == 3) {
			uint32_t value = a == 8 ? core->busRead8(core, b) : a == 16 ? core->busRead16(core, b) : core->busRead32(core, b);
			printf("ok %" PRIu32 "\n", value);
		} else if (!strcmp(command, "write") && count == 4) {
			if (a == 8) {
				core->busWrite8(core, b, c);
			} else if (a == 16) {
				core->busWrite16(core, b, c);
			} else {
				core->busWrite32(core, b, c);
			}
			printf("ok\n");
		} else if (!strcmp(command, "screen")) {
			size_t size = (size_t) width * height * sizeof(color_t);
			printf("ok %zu\n", size);
			fflush(stdout);
			fwrite(video, 1, size, stdout);
		} else if (!strcmp(command, "quit")) {
			break;
		} else {
			printf("error unknown command\n");
		}
		fflush(stdout);
	}
	core->deinit(core);
	free(video);
	return 0;
}
