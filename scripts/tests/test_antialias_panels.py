"""Tests for the in-place antialiasing of the panel PNGs."""

# cspell:ignore antialias gmic

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import antialias_panels as ap
from PIL import Image

if TYPE_CHECKING:
    import pytest

ORIGINAL = (10, 20, 30)
SMOOTHED = (200, 100, 50)


def _png(path: Path, mode: str = "RGB", colour: tuple[int, ...] = ORIGINAL) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new(mode, (8, 6), colour).save(path)
    return path


def _pixel(path: Path) -> tuple[int, ...]:
    with Image.open(path) as image:
        return image.convert("RGB").getpixel((0, 0))  # ty: ignore[invalid-return-type]


def _fake_filter(source: Path, target: Path) -> None:
    """Write a copy of the same size and mode in another colour."""
    with Image.open(source) as image:
        fill = SMOOTHED if image.mode == "RGB" else (*SMOOTHED, 255)
        Image.new(image.mode, image.size, fill).save(target, format="PNG")


def _wrong_size_filter(_source: Path, target: Path) -> None:
    Image.new("RGB", (3, 3), SMOOTHED).save(target, format="PNG")


def _failing_filter(_source: Path, _target: Path) -> None:
    raise subprocess.CalledProcessError(1, "gmic")


def _tree(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "panels", tmp_path / "backup"


def _run(root: Path, backup: Path, *extra: str, run_filter: ap.Filter = _fake_filter) -> int:
    return ap.main(["--root", str(root), "--backup-dir", str(backup), *extra], run_filter)


class TestGmicArgs:
    def test_the_amplitude_is_divided_by_three_as_the_gui_filter_does(self) -> None:
        args = ap.gmic_args(2)

        assert "smooth.." in args
        assert args[args.index("smooth..") + 1] == ".,{2/3},0.5,120,2,1"

    def test_the_result_is_cut_to_eight_bits(self) -> None:
        assert ap.gmic_args(2)[-2:] == ["c", "0,255"]


class TestGmicFilter:
    def test_gmic_only_sees_names_the_script_chose(self, tmp_path: Path) -> None:
        source = _png(tmp_path / "odd, name.png")
        target = tmp_path / "out.png"

        def fake_run(command: list[str], **_kwargs: object) -> None:
            assert Path(command[3]).name == "in.png"
            assert command[-2] == "o"
            _png(Path(command[-1]), colour=SMOOTHED)

        with patch.object(ap.subprocess, "run", side_effect=fake_run) as run:
            ap.gmic_filter(2)(source, target)

        assert run.call_count == 1
        assert _pixel(target) == SMOOTHED


class TestHasTransparency:
    def test_an_opaque_alpha_channel_is_not_transparency(self, tmp_path: Path) -> None:
        assert not ap.has_transparency(_png(tmp_path / "a.png", "RGBA", (1, 2, 3, 255)))

    def test_no_alpha_channel_is_not_transparency(self, tmp_path: Path) -> None:
        assert not ap.has_transparency(_png(tmp_path / "a.png"))

    def test_one_see_through_pixel_is(self, tmp_path: Path) -> None:
        image = Image.new("RGBA", (4, 4), (1, 2, 3, 255))
        image.putpixel((2, 2), (1, 2, 3, 254))
        image.save(tmp_path / "a.png")

        assert ap.has_transparency(tmp_path / "a.png")


class TestMakePlan:
    def test_every_reason_to_skip_is_sorted_out(self, tmp_path: Path) -> None:
        root, backup = _tree(tmp_path)
        _png(root / "Favourites" / "Title" / "001.png")
        _png(root / "Favourites" / "Title" / "001-flipped.png")
        _png(root / "Favourites" / "Title" / "done.png")
        _png(backup / "Favourites" / "Title" / "done.png")
        _png(root / "Insets" / "clear.png", "RGBA", (1, 2, 3, 0))
        (root / "Covers").mkdir()
        (root / "Covers" / "cover.jpg").write_bytes(b"jpeg")
        _png(root / "AI" / "Title" / "001-pastel.png")

        plan = ap.make_plan(root, backup, [], ["AI/*", "*-flipped.png"])

        assert plan.process == [Path("Favourites/Title/001.png")]
        assert plan.skipped == {
            ap.EXCLUDED: [
                Path("AI/Title/001-pastel.png"),
                Path("Favourites/Title/001-flipped.png"),
            ],
            ap.NOT_PNG: [Path("Covers/cover.jpg")],
            ap.DONE: [Path("Favourites/Title/done.png")],
            ap.TRANSPARENT: [Path("Insets/clear.png")],
        }

    def test_a_jpeg_named_as_a_png_is_not_a_png(self, tmp_path: Path) -> None:
        root, backup = _tree(tmp_path)
        (root / "Silhouettes").mkdir(parents=True)
        Image.new("RGB", (8, 6), ORIGINAL).save(root / "Silhouettes" / "a.png", format="JPEG")

        plan = ap.make_plan(root, backup, [], [])

        assert plan.process == []
        assert plan.skipped == {ap.NOT_PNG: [Path("Silhouettes/a.png")]}

    def test_only_the_included_folders_are_looked_in(self, tmp_path: Path) -> None:
        root, backup = _tree(tmp_path)
        _png(root / "Favourites" / "a.png")
        _png(root / "Insets" / "b.png")

        plan = ap.make_plan(root, backup, ["Insets"], [])

        assert plan.process == [Path("Insets/b.png")]
        assert plan.skipped == {}


class TestApply:
    def test_a_file_is_replaced_and_its_original_kept(self, tmp_path: Path) -> None:
        root, backup = _tree(tmp_path)
        panel = _png(root / "Favourites" / "Title" / "001.png")

        assert _run(root, backup, "--apply") == 0

        assert _pixel(panel) == SMOOTHED
        assert _pixel(backup / "Favourites" / "Title" / "001.png") == ORIGINAL
        assert [p.name for p in panel.parent.iterdir()] == ["001.png"]

    def test_a_second_run_smooths_nothing_twice(self, tmp_path: Path) -> None:
        root, backup = _tree(tmp_path)
        _png(root / "Favourites" / "001.png")
        _run(root, backup, "--apply")
        calls: list[Path] = []

        def counting(source: Path, target: Path) -> None:
            calls.append(source)
            _fake_filter(source, target)

        assert _run(root, backup, "--apply", run_filter=counting) == 0

        assert calls == []
        assert _pixel(backup / "Favourites" / "001.png") == ORIGINAL

    def test_without_apply_nothing_changes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, backup = _tree(tmp_path)
        panel = _png(root / "Favourites" / "001.png")

        assert _run(root, backup) == 0

        assert _pixel(panel) == ORIGINAL
        assert not backup.exists()
        out = capsys.readouterr().out
        assert "to smooth: 1" in out
        assert "  Favourites: 1" in out
        assert "nothing changed" in out

    def test_an_opaque_alpha_channel_is_kept(self, tmp_path: Path) -> None:
        root, backup = _tree(tmp_path)
        panel = _png(root / "Insets" / "a.png", "RGBA", (1, 2, 3, 255))

        assert _run(root, backup, "--apply") == 0

        with Image.open(panel) as image:
            assert image.mode == "RGBA"
        assert _pixel(panel) == SMOOTHED

    def test_a_copy_of_another_size_leaves_the_original(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, backup = _tree(tmp_path)
        panel = _png(root / "Favourites" / "001.png")

        assert _run(root, backup, "--apply", run_filter=_wrong_size_filter) == 1

        assert _pixel(panel) == ORIGINAL
        assert not backup.exists()
        assert [p.name for p in panel.parent.iterdir()] == ["001.png"]
        assert "FAILED Favourites/001.png" in capsys.readouterr().out

    def test_a_failed_file_does_not_stop_the_rest(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, backup = _tree(tmp_path)
        first = _png(root / "Favourites" / "001.png")
        second = _png(root / "Favourites" / "002.png")

        def fails_on_first(source: Path, target: Path) -> None:
            if source == first:
                _failing_filter(source, target)
            _fake_filter(source, target)

        assert _run(root, backup, "--apply", run_filter=fails_on_first) == 1

        assert _pixel(first) == ORIGINAL
        assert _pixel(second) == SMOOTHED
        assert "smoothed 1, failed 1" in capsys.readouterr().out

    def test_progress_is_said_every_hundred_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, backup = _tree(tmp_path)
        for number in range(100):
            _png(root / "Favourites" / f"{number:03d}.png")

        assert _run(root, backup, "--apply") == 0

        assert "  100 of 100" in capsys.readouterr().out


class TestReport:
    def test_transparent_files_are_always_named(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, backup = _tree(tmp_path)
        _png(root / "Insets" / "clear.png", "RGBA", (1, 2, 3, 0))
        (root / "Insets" / "notes.txt").write_text("x")

        _run(root, backup)

        out = capsys.readouterr().out
        assert f"skipped, {ap.TRANSPARENT}: 1\n  Insets/clear.png" in out
        assert f"skipped, {ap.NOT_PNG}: 1\n" in out
        assert "notes.txt" not in out

    def test_verbose_names_every_skipped_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, backup = _tree(tmp_path)
        (root / "Insets").mkdir(parents=True)
        (root / "Insets" / "notes.txt").write_text("x")

        _run(root, backup, "--verbose")

        assert "  Insets/notes.txt" in capsys.readouterr().out


class TestRestore:
    def test_the_originals_come_back_and_the_backups_go(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, backup = _tree(tmp_path)
        panel = _png(root / "Favourites" / "Title" / "001.png")
        _run(root, backup, "--apply")

        assert _run(root, backup, "--restore") == 0

        assert _pixel(panel) == ORIGINAL
        assert not (backup / "Favourites" / "Title" / "001.png").exists()
        assert "restored 1" in capsys.readouterr().out

    def test_a_restored_file_can_be_smoothed_again(self, tmp_path: Path) -> None:
        root, backup = _tree(tmp_path)
        panel = _png(root / "Favourites" / "001.png")
        _run(root, backup, "--apply")
        _run(root, backup, "--restore")

        assert _run(root, backup, "--apply") == 0

        assert _pixel(panel) == SMOOTHED


class TestArguments:
    def test_a_missing_root_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert _run(tmp_path / "nowhere", tmp_path / "backup") == 1
        assert "no such folder" in capsys.readouterr().out

    def test_a_backup_folder_inside_the_panels_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, _ = _tree(tmp_path)
        _png(root / "Favourites" / "001.png")

        assert _run(root, root / "backup", "--apply") == 1
        assert _run(root, root, "--apply") == 1

        assert "must be outside" in capsys.readouterr().out
        assert _pixel(root / "Favourites" / "001.png") == ORIGINAL

    def test_an_unknown_include_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, backup = _tree(tmp_path)
        _png(root / "Favourites" / "001.png")

        assert _run(root, backup, "--include", "Favorites", "--apply") == 1

        assert "Favorites" in capsys.readouterr().out
        assert _pixel(root / "Favourites" / "001.png") == ORIGINAL

    def test_apply_without_gmic_says_how_to_get_it(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root, backup = _tree(tmp_path)
        panel = _png(root / "Favourites" / "001.png")

        with patch.object(ap.shutil, "which", return_value=None):
            status = ap.main(["--root", str(root), "--backup-dir", str(backup), "--apply"])

        assert status == 1
        assert "apt install gmic" in capsys.readouterr().out
        assert _pixel(panel) == ORIGINAL

    def test_apply_with_gmic_uses_the_gmic_filter(self, tmp_path: Path) -> None:
        root, backup = _tree(tmp_path)
        panel = _png(root / "Favourites" / "001.png")

        with (
            patch.object(ap.shutil, "which", return_value="/usr/bin/gmic"),
            patch.object(ap, "gmic_filter", return_value=_fake_filter) as make,
        ):
            status = ap.main(
                ["--root", str(root), "--backup-dir", str(backup), "--apply", "--amplitude", "1"]
            )

        assert status == 0
        make.assert_called_once_with(1.0)
        assert _pixel(panel) == SMOOTHED
