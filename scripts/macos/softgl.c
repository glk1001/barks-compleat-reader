// Let Kivy draw on macOS with no GPU driver (a VirtualBox guest), on Apple's software
// OpenGL renderer.
//
// Kivy's SDL2 asks for a hardware-accelerated visual (SDL_GL_ACCELERATED_VISUAL = 1),
// which macOS refuses when its only renderer is the software one: "Failed creating OpenGL
// pixel format". Loaded through DYLD_INSERT_LIBRARIES, this interposes
// SDL_GL_SetAttribute and turns that one request into "any renderer": -1, SDL's own
// "either is fine", under which macOS still picks a GPU when there is one. (0 would ask
// for the software renderer by name, even on a Mac with a GPU.) Built and loaded by
// with-soft-gl.sh.
//
// Once loaded it takes itself out of DYLD_INSERT_LIBRARIES, so the process it was meant
// for keeps it and nothing that process starts inherits it: on Apple silicon, Apple's own
// programs are arm64e, and dyld kills one asked to insert this arm64 library ("Abort trap:
// 6" from `sleep` under a test). Its path is left in BARKS_SOFT_GL_LIBRARY, for a parent
// that does want its children to have it (pytest's workers: the root conftest.py).
// cspell:ignore softgl interposes interposers dladdr dlfcn strsep strdup

#include <dlfcn.h>
#include <stdlib.h>
#include <string.h>

extern int SDL_GL_SetAttribute(int attr, int value);

static const int SDL_GL_ACCELERATED_VISUAL = 15;
static const int ANY_RENDERER = -1;
static const char *const INSERTED = "DYLD_INSERT_LIBRARIES";
static const char *const SAVED = "BARKS_SOFT_GL_LIBRARY";

static int softgl_set_attribute(int attr, int value) {
    if (attr == SDL_GL_ACCELERATED_VISUAL) {
        value = ANY_RENDERER;
    }
    return SDL_GL_SetAttribute(attr, value);
}

__attribute__((used)) static const struct {
    const void *replacement;
    const void *original;
} interposers[] __attribute__((section("__DATA,__interpose"))) = {
    {(const void *)softgl_set_attribute, (const void *)SDL_GL_SetAttribute},
};

// Drop this library's entry from DYLD_INSERT_LIBRARIES, keeping any others, before the
// program's main (and Python's copy of the environment) runs.
__attribute__((constructor)) static void softgl_leave_the_environment(void) {
    Dl_info self;
    const char *list = getenv(INSERTED);
    if (list == NULL || dladdr((const void *)softgl_set_attribute, &self) == 0 ||
        self.dli_fname == NULL) {
        return;
    }
    char *entries = strdup(list);
    char *kept = calloc(strlen(list) + 1, 1);
    if (entries == NULL || kept == NULL) {
        free(entries);
        free(kept);
        return;
    }
    char *cursor = entries;
    char *entry;
    while ((entry = strsep(&cursor, ":")) != NULL) {
        if (*entry == '\0' || strcmp(entry, self.dli_fname) == 0) {
            continue;
        }
        if (*kept != '\0') {
            strcat(kept, ":");
        }
        strcat(kept, entry);
    }
    setenv(SAVED, self.dli_fname, 1);
    if (*kept == '\0') {
        unsetenv(INSERTED);
    } else {
        setenv(INSERTED, kept, 1);
    }
    free(entries);
    free(kept);
}
