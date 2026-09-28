"""Tests for the OS name, VM detection and file hash helpers."""

from __future__ import annotations

import hashlib
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from comic_utils import sys_utils

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def test_the_hash_is_the_files_sha256(tmp_path: Path) -> None:
    file = tmp_path / "page.jpg"
    file.write_bytes(b"\x00\x01barks")
    assert sys_utils.get_hash_str(file) == hashlib.sha256(b"\x00\x01barks").hexdigest()


class TestGetOsName:
    @pytest.mark.parametrize(
        ("system", "name"),
        [("Windows", "Windows"), ("Darwin", "macOS"), ("SunOS", "Unknown")],
    )
    def test_each_system_by_its_usual_name(self, system: str, name: str) -> None:
        with patch.object(sys_utils.platform, "system", return_value=system):
            assert sys_utils.get_os_name() == name

    def test_linux_is_named_by_its_distribution(self) -> None:
        with (
            patch.object(sys_utils.platform, "system", return_value="Linux"),
            patch.object(sys_utils.distro, "name", return_value=" Ubuntu 26.04 LTS "),
        ):
            assert sys_utils.get_os_name() == "Ubuntu 26.04 LTS"

    def test_a_linux_with_no_distribution_name_is_linux(self) -> None:
        with (
            patch.object(sys_utils.platform, "system", return_value="Linux"),
            patch.object(sys_utils.distro, "name", return_value=""),
        ):
            assert sys_utils.get_os_name() == "Linux"


def _detect_virt(returncode: int) -> subprocess.CompletedProcess[bytes]:
    return subprocess.CompletedProcess(args=[], returncode=returncode)


class TestIsVirtualMachineOnLinux:
    @pytest.fixture(autouse=True)
    def linux(self) -> Iterator[None]:
        with patch.object(sys_utils.platform, "system", return_value="Linux"):
            yield

    def test_systemd_detect_virt_answers_by_exit_status(self) -> None:
        """--quiet prints nothing either way: a VM was once read as not one."""
        with patch.object(sys_utils.subprocess, "run", return_value=_detect_virt(0)):
            assert sys_utils.is_virtual_machine() is True
        with patch.object(sys_utils.subprocess, "run", return_value=_detect_virt(1)):
            assert sys_utils.is_virtual_machine() is False

    @pytest.mark.parametrize(
        ("product", "vm"),
        [("VirtualBox\n", True), ("KVM\n", True), ("Precision 7865 Tower\n", False)],
    )
    def test_without_systemd_the_dmi_strings_decide(
        self, tmp_path: Path, product: str, vm: bool
    ) -> None:
        (tmp_path / "product_name").write_text(product)
        with (
            patch.object(sys_utils.subprocess, "run", side_effect=FileNotFoundError),
            patch.object(sys_utils, "DMI_FILES", (tmp_path / "product_name", tmp_path / "missing")),
        ):
            assert sys_utils.is_virtual_machine() is vm


class TestIsVirtualMachineElsewhere:
    @pytest.mark.parametrize(
        ("system", "output", "vm"),
        [
            ("Windows", "System Model: VirtualBox", True),
            ("Windows", "System Model: Precision 7865 Tower", False),
            ("Darwin", "machdep.cpu.brand_string: VMware Virtual Platform", True),
            ("Darwin", "machdep.cpu.brand_string: Apple M2", False),
        ],
    )
    def test_the_system_report_names_the_hypervisor(
        self, system: str, output: str, vm: bool
    ) -> None:
        with (
            patch.object(sys_utils.platform, "system", return_value=system),
            patch.object(sys_utils.subprocess, "check_output", return_value=output),
        ):
            assert sys_utils.is_virtual_machine() is vm

    @pytest.mark.parametrize("system", ["Windows", "Darwin"])
    def test_a_failing_report_is_not_a_vm(self, system: str) -> None:
        with (
            patch.object(sys_utils.platform, "system", return_value=system),
            patch.object(sys_utils.subprocess, "check_output", side_effect=OSError),
        ):
            assert sys_utils.is_virtual_machine() is False

    def test_an_unknown_system_is_not_a_vm(self) -> None:
        with patch.object(sys_utils.platform, "system", return_value="SunOS"):
            assert sys_utils.is_virtual_machine() is False
