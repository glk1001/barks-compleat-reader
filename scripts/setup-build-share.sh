#!/usr/bin/env bash
# cspell:ignore cifs mountpoint NOPASSWD
#
# Let this machine's overnight build-check read the comic library from another
# machine's read-only Samba share, mounted only while that stage runs.
#
# build-check reads the whole comic build tree under ~/Books/Carl Barks, about
# 330 GB, which a second machine need not hold. Run this once, as root, on that
# machine; the share is the one scripts/samba/barks-library.conf defines on the
# machine that holds the library:
#
#   sudo bash scripts/setup-build-share.sh //HOST/BarksLibrary
#
# It writes:
#   /etc/barks-build-share.conf       the share, where it mounts, and how;
#                                     run_overnight.sh's build-check stage reads it
#   /etc/sudoers.d/barks-build-share  lets the user who ran sudo (or USER, the second
#                                     argument) run exactly that mount and its
#                                     unmount with no password, and nothing else
#   /mnt/barks-library                the mount point
# and then mounts the share once, checks it holds the library, and unmounts it.
#
# Needs cifs-utils (mount.cifs). To undo:
#   sudo rm /etc/barks-build-share.conf /etc/sudoers.d/barks-build-share
#
# Usage: sudo bash scripts/setup-build-share.sh //HOST/SHARE [USER]
set -euo pipefail

share="${1:?usage: sudo bash scripts/setup-build-share.sh //HOST/SHARE [USER]}"
user="${2:-${SUDO_USER:-}}"
MOUNT_DIR=/mnt/barks-library
CONF=/etc/barks-build-share.conf
SUDOERS=/etc/sudoers.d/barks-build-share

die() {
    echo "setup-build-share: $*" >&2
    exit 1
}
((EUID == 0)) || die "run it with sudo"
[[ -n "$user" ]] || die "name the user who runs the overnight suite (second argument)"
id "$user" >/dev/null 2>&1 || die "no such user: $user"
[[ "$share" =~ ^//[^/[:space:]]+/[^/[:space:]]+$ ]] || die "the share must look like //HOST/SHARE, not '$share'"
command -v mount.cifs >/dev/null || die "install cifs-utils first: sudo apt install cifs-utils"
[[ -x /usr/bin/mount && -x /usr/bin/umount ]] || die "no /usr/bin/mount or /usr/bin/umount"

# Read-only, as a guest (the share needs no password), every file owned by the user.
options="ro,guest,uid=$(id -u "$user"),gid=$(id -g "$user"),file_mode=0444,dir_mode=0555"
mount_cmd="/usr/bin/mount -t cifs -o ${options} ${share} ${MOUNT_DIR}"
umount_cmd="/usr/bin/umount ${MOUNT_DIR}"

mkdir -p "$MOUNT_DIR"

# In a sudoers command's arguments, commas, colons, equals signs and backslashes are
# escaped; the rule then matches the command run_overnight.sh runs, word for word.
escape() { sed 's/[\\,:=]/\\&/g' <<<"$1"; }
rule_file="$(mktemp)"
trap 'rm -f "$rule_file"' EXIT
{
    echo "# Written by barks-compleat-reader's scripts/setup-build-share.sh: the overnight"
    echo "# build-check stage mounts the comic library's share for its run, and nothing else."
    echo "${user} ALL=(root) NOPASSWD: $(escape "$mount_cmd"), $(escape "$umount_cmd")"
} >"$rule_file"
visudo -cf "$rule_file" >/dev/null || {
    cat "$rule_file" >&2
    die "the rule above failed visudo's check; nothing was installed"
}
install -m 0440 -o root -g root "$rule_file" "$SUDOERS"

cat >"$CONF" <<EOF
# Written by scripts/setup-build-share.sh; read by run_overnight.sh's build-check stage.
BUILD_SHARE=${share}
BUILD_SHARE_MOUNT_DIR=${MOUNT_DIR}
BUILD_SHARE_OPTIONS=${options}
EOF
chmod 0644 "$CONF"

echo "setup-build-share: mounting ${share} once, to check it"
mountpoint -q "$MOUNT_DIR" && /usr/bin/umount "$MOUNT_DIR"
if ! $mount_cmd; then
    die "could not mount ${share}: is that machine on, and its share defined?"
fi
found="$(find "$MOUNT_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l)"
if [[ -d "${MOUNT_DIR}/Fantagraphics-original" ]]; then
    echo "setup-build-share: OK - ${found} folders there, Fantagraphics-original among them"
    status=0
else
    echo "setup-build-share: mounted, but no Fantagraphics-original there: is it the comic library?"
    status=1
fi
$umount_cmd
echo "setup-build-share: ${user} may now run the build-check stage; it mounts the share for its run"
exit "$status"
