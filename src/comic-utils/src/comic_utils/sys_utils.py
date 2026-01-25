import hashlib
import os
import platform
import subprocess
from pathlib import Path

import distro


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
def is_virtual_machine() -> bool:  # noqa: PLR0911
    system = platform.system()

    # -------------------------
    # Linux
    # -------------------------
    if system == "Linux":
        # Check systemd-detect-virt (very reliable)
        try:
            out = subprocess.check_output(
                ["systemd-detect-virt", "--vm", "--quiet"],  # noqa: S607
                stderr=subprocess.DEVNULL,
            )
        except Exception:  # noqa: BLE001, S110
            pass
        else:
            return out != b""

        # Fallback: look at DMI strings
        dmi_files = [
            "/sys/class/dmi/id/product_name",
            "/sys/class/dmi/id/sys_vendor",
            "/sys/class/dmi/id/board_vendor",
        ]
        vm_signatures = [
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
        ]

        for path in dmi_files:
            if os.path.exists(path):  # noqa: PTH110
                try:
                    data = open(path).read().lower()  # noqa: PTH123, SIM115
                    if any(sig in data for sig in vm_signatures):
                        return True
                except Exception:  # noqa: BLE001, S110
                    pass

        return False

    # -------------------------
    # Windows
    # -------------------------
    if system == "Windows":
        try:
            # noinspection LongLine
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
            # noinspection LongLine
            out = subprocess.check_output(["sysctl", "machdep.cpu.brand_string"], text=True).lower()  # noqa: S607

            if "virtualbox" in out or "vmware" in out:
                return True

        except Exception:  # noqa: BLE001, S110
            pass

        return False

    # Unknown OS
    return False
