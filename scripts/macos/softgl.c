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
// cspell:ignore softgl interposes interposers

extern int SDL_GL_SetAttribute(int attr, int value);

static const int SDL_GL_ACCELERATED_VISUAL = 15;
static const int ANY_RENDERER = -1;

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
