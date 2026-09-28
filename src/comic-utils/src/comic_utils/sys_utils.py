import hashlib
import platform
import subprocess
from pathlib import Path

import distro

# Where Linux exposes the machine's DMI identity, and what a hypervisor writes there.
DMI_FILES = (
    Path("/sys/class/dmi/id/product_name"),
    Path("/sys/class/dmi/id/sys_vendor"),
    Path("/sys/class/dmi/id/board_vendor"),
)
VM_SIGNATURES = (
    "vmware",
    "virtualbox",
    "qemu",
    "kvm",
    "microsoft corporation",
    "xen",
    "parallels",
    "bhyve",
    "innotek",
    "virtio",
)


def get_hash_str(file: Path) -> str:
    with file.open("rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def get_os_name() -> str:
    """Return a human-readable OS name.

    Examples:
      - Windows
      - macOS
      - Ubuntu, Fedora, Arch, etc. (Linux distros)
      - Unknown

    """
    system = platform.system()

    # Windows
    if system == "Windows":
        return "Windows"

    # macOS
    if system == "Darwin":
        return "macOS"

    # Linux (use distro package if available)
    if system == "Linux":
        name = distro.name(pretty=True).strip()
        if name:
            return name

        # fallback
        return "Linux"

    # Everything else
    return "Unknown"


# noinspection PyBroadException
def is_virtual_machine() -> bool:  # noqa: C901, PLR0911
    system = platform.system()

    # -------------------------
    # Linux
    # -------------------------
    if system == "Linux":
        # systemd-detect-virt (very reliable) answers in its exit status: --quiet
        # prints nothing either way, 0 is a VM and anything else is not.
        try:
            result = subprocess.run(
                ["systemd-detect-virt", "--vm", "--quiet"],  # noqa: S607
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            pass  # not installed: fall back to the DMI strings
        else:
            return result.returncode == 0

        for path in DMI_FILES:
            try:
                data = path.read_text().lower()
            except OSError:
                continue
            if any(sig in data for sig in VM_SIGNATURES):
                return True

        return False

    # -------------------------
    # Windows
    # -------------------------
    if system == "Windows":
        try:
            out = subprocess.check_output(["systeminfo"], text=True, errors="ignore").lower()  # noqa: S607

            vm_keywords = ["virtualbox", "vmware", "hyper-v", "kvm", "qemu", "parallels", "xen"]

            if any(k in out for k in vm_keywords):
                return True

        except Exception:  # noqa: BLE001, S110
            pass

        return False

    # -------------------------
    # macOS
    # -------------------------
    if system == "Darwin":
        try:
            out = subprocess.check_output(["sysctl", "machdep.cpu.brand_string"], text=True).lower()  # noqa: S607

            if "virtualbox" in out or "vmware" in out:
                return True

        except Exception:  # noqa: BLE001, S110
            pass

        return False

    # Unknown OS
    return False
