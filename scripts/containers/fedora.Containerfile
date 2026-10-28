# The Fedora image scripts/run_overnight_container.sh runs a slice of the overnight
# run in: the dnf equivalents of docs/setup.md's apt packages, headless only (Xvfb, no
# Xephyr), and uv at the host's version. Fedora's current release, as a user installing
# today would have it: the runner builds with --pull=newer, so a new release or update
# of the base image is picked up on the next run, and the run logs which one it was.
#
# Build context: scripts/containers (nothing is copied in from it).
ARG UV_VERSION=0.13.0
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

FROM registry.fedoraproject.org/fedora:latest

# gcc, patchelf, ccache: the Nuitka build (build.sh). Xvfb, xvfb-run, xauth: every
# display a run needs. xautomation (xte), xdpyinfo, xwininfo, ImageMagick, xclip,
# xdotool: the GUI probe and the smoke test's Escape. mesa: software OpenGL on Xvfb.
# The X libraries: what Kivy's bundled SDL loads. procps-ng: pgrep and ps, which the
# GUI runners use to find and stop what they started.
RUN dnf install -y --setopt=install_weak_deps=False \
        git gcc gcc-c++ patchelf ccache make \
        xorg-x11-server-Xvfb xvfb-run xorg-x11-xauth \
        xautomation xdpyinfo xwininfo ImageMagick xclip xdotool \
        mesa-dri-drivers mesa-libGL mesa-libEGL libglvnd-glx libglvnd-egl \
        libX11 libXext libXrender libXrandr libXcursor libXi libXinerama libXScrnSaver \
        libXxf86vm mtdev fontconfig dejavu-sans-fonts \
        procps-ng findutils which tar gzip unzip zstd diffutils hostname \
    && dnf clean all

COPY --from=uv /uv /uvx /usr/local/bin/

ENV LANG=C.UTF-8
