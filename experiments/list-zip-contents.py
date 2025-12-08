# ruff: noqa: T201

"""A utility script to list all files and directories within a zip archive."""

import argparse
import sys
import zipfile
from pathlib import Path


def list_zip_contents(zip_filepath: Path) -> None:
    """Open a zip file and print the name of each member in the archive."""
    if not zip_filepath.exists():
        print(f"Error: File not found at '{zip_filepath}'", file=sys.stderr)
        sys.exit(1)

    if not zip_filepath.is_file():
        print(f"Error: Path '{zip_filepath}' is not a file.", file=sys.stderr)
        sys.exit(1)

    try:
        with zipfile.ZipFile(zip_filepath, "r") as zip_ref:
            print(f"Contents of '{zip_filepath.name}':")
            print("-" * 30)
            # namelist() returns a list of all members in the archive
            for member_name in zip_ref.namelist():
                zip_path = zipfile.Path(zip_ref, at=str(member_name))
                # Check if the member is a file before trying to read it.
                if zip_path.is_dir():
                    print(f"{member_name} [directory]")
                elif zip_path.is_file():
                    file_info = zip_ref.getinfo(member_name)
                    print(f"{member_name} [file, {file_info.file_size} bytes]")
                    zip_bytes = zip_path.read_bytes()
                    print(f"Successfully read {len(zip_bytes)} bytes]")
            print("-" * 30)
            print(f"Total members: {len(zip_ref.namelist())}")

    except zipfile.BadZipFile:
        print(f"Error: '{zip_filepath}' is not a valid zip file.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Parse command-line arguments and initiate the zip listing."""
    parser = argparse.ArgumentParser(description="List the contents of a zip file.")
    parser.add_argument("zip_filepath", type=Path, help="The path to the zip file to inspect.")
    args = parser.parse_args()
    list_zip_contents(args.zip_filepath)


if __name__ == "__main__":
    main()
