# ruff: noqa: T201

import os
import shutil
import zipfile
from pathlib import Path

from comic_utils.pyminizip_file_collector import MiniZipFileCollector


# Example 1: Simple migration from zipfile pattern.
def old_zipfile_pattern() -> None:
    """Your old pattern with zipfile."""
    base_dir = Path("images")
    with zipfile.ZipFile("output.zip", "w") as zf:
        for file in base_dir.rglob("*.jpg"):
            zf.write(file, arcname=file.relative_to(base_dir))


def new_pyminizip_pattern() -> None:
    """Use pyminizip zip pattern - very similar to zipfile."""
    base_dir = Path("images")

    with MiniZipFileCollector("output.zip", "password123", base_dir=base_dir) as zf:
        for file in base_dir.rglob("*.jpg"):
            zf.add_file(file)
    # ZIP is automatically created when exiting the context.


# Example 2: With filtering/processing
def with_filtering() -> None:
    """Add files with custom logic."""
    base_dir = Path("images")

    with MiniZipFileCollector("filtered.zip", "password123", base_dir=base_dir) as zf:
        for file in base_dir.rglob("*"):
            if file.is_file():  # noqa: SIM102
                # Custom filtering.
                if file.suffix.lower() in [".jpg", ".png", ".gif"]:  # noqa: SIM102
                    # Custom processing.
                    if file.stat().st_size > 1024:  # Only files > 1KB  # noqa: PLR2004
                        zf.add_file(file)
                        print(f"Added: {file.name}")


# Example 3: With custom archive names
def with_custom_names() -> None:
    """Add files with custom paths in ZIP."""
    with MiniZipFileCollector("custom.zip", "password123") as zf:
        # Add to specific subdirectories.
        zf.add_file("photo1.jpg", arcname="photos/2024/photo1.jpg")
        zf.add_file("photo2.jpg", arcname="photos/2024/photo2.jpg")
        zf.add_file("readme.txt", arcname="docs/readme.txt")


# Example 4: Manual control (no context manager)
def manual_control() -> None:
    """Manual control over when ZIP is created."""
    collector = MiniZipFileCollector("manual.zip", "password123", base_dir=Path("images"))

    for file in Path("images").rglob("*.jpg"):
        collector.add_file(file)
        # Do other processing...

    # Create ZIP when ready.
    collector.write()


def do_filtered_collect(
    archive_filename: str, password: str, base_dir: Path, exts: set[str]
) -> None:
    with MiniZipFileCollector(archive_filename, password, base_dir=base_dir) as zf:
        for file in base_dir.rglob("*"):
            if file.suffix.lower() in exts:
                print(f'Collecting: "{file.relative_to(base_dir)}".')
                zf.add_file(file)
        print(f'Created "{zf.output_zip}" with {len(zf.file_paths)} files.')


def check_read_zipfile_paths(archive_filename: str, password: str) -> None:
    with zipfile.ZipFile(archive_filename, "r") as zf:
        zf.setpassword(password.encode("utf-8"))
        zipfile_path = zipfile.Path(zf)

        print(zipfile_path)
        for entry_path in zipfile_path.iterdir():
            print(f'- "{entry_path}".')

            # If it's a file, you can read its content.
            if entry_path.is_file():
                with entry_path.open("r") as f:
                    content = f.read()
                    print(f"  Content: '{content}'")

            # If it's a directory, you can iterate through its contents recursively.
            if entry_path.is_dir():
                print(f'  Contents of directory "{entry_path.name}":')
                for sub_entry_path in entry_path.iterdir():
                    print(f"  - {sub_entry_path}")
                    if sub_entry_path.is_file():
                        with sub_entry_path.open("r") as f:
                            content = f.read()
                            print(f"    Content: '{content}'")


if __name__ == "__main__":
    # Create test structure.
    shutil.rmtree("temp", ignore_errors=True)

    test_dir = Path("temp/test_images")
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "subdir").mkdir(exist_ok=True)

    (test_dir / "image1.jpg").write_bytes(b"fake image 1")
    (test_dir / "image2.jpg").write_bytes(b"fake image 2")
    (test_dir / "image3.png").write_bytes(b"fake image 2")
    (test_dir / "subdir" / "image4.jpg").write_bytes(b"fake image 4")
    (test_dir / "subdir" / "image5.png").write_bytes(b"fake image 5")

    print("=" * 60)
    print("Creating password-protected ZIP with collected files")
    print("=" * 60)

    ZIP_PASSWORD = os.environ["BARKS_PANELS_PW"]
    zip_filename = "collected.zip"

    # Use the new pattern.
    allowed_exts = {".jpg", ".png"}
    do_filtered_collect(zip_filename, ZIP_PASSWORD, test_dir, allowed_exts)

    # Verify with zipfile.Path.
    print("\n" + "=" * 60)
    print("Reading with zipfile.Path...")
    print("=" * 60)

    check_read_zipfile_paths(zip_filename, ZIP_PASSWORD)
