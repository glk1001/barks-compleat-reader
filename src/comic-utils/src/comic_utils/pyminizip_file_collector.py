"""Helper for collecting files and creating password-protected ZIPs with pyminizip."""

import shutil
import tempfile
from pathlib import Path

import pyminizip  # type: ignore[import-untyped]


class MiniZipFileCollector:
    """Collects files for pyminizip batch processing while mimicking zipfile iteration pattern."""

    def __init__(
        self,
        output_zip: Path | str,
        password: str,
        base_dir: Path | None = None,
        compression_level: int = 0,
    ) -> None:
        """Initialize collector.

        Args:
            output_zip: Output ZIP filename
            password: Password as string
            base_dir: Base directory for relative paths (if None, uses absolute paths)
            compression_level: 0-9, use 0 for images (no compression)

        """
        self.output_zip = str(output_zip)
        self.password = password
        self.base_dir = base_dir
        self.compression_level = compression_level
        self.file_paths = []
        self.prefixes = []
        self._temp_dirs = []  # Track temporary directories for cleanup

    def add_file(self, file_path: Path | str, arcname: str | None = None) -> None:
        """Add a file to be zipped (mimics zipfile.write interface).

        Args:
            file_path: Path to file to add
            arcname: Archive name (path in ZIP). If None, calculates from base_dir

        """
        file_path = Path(file_path)

        if not file_path.is_file():
            msg = f'"{file_path}" not found'
            raise FileNotFoundError(msg)

        self.file_paths.append(str(file_path))

        if arcname:
            # Use provided arcname.
            arc_path = Path(arcname)
            prefix = str(arc_path.parent) + "/" if arc_path.parent != Path() else ""
        elif self.base_dir:
            # Calculate relative to base_dir.
            rel_path = file_path.relative_to(self.base_dir)
            prefix = str(rel_path.parent) + "/" if rel_path.parent != Path() else ""
        else:
            # Use file's own parent directory.
            prefix = str(file_path.parent) + "/" if file_path.parent != Path() else ""

        self.prefixes.append(prefix)

    def add_str(self, arcname: str, data: str | bytes) -> None:
        """Add string/bytes data to ZIP (mimics zipfile.writestr interface).

        Args:
            arcname: Archive name (path in ZIP)
            data: String or bytes data to write

        """
        # Convert string to bytes if needed.
        if isinstance(data, str):
            data = data.encode("utf-8")

        # Parse the arcname to get directory and filename.
        arc_path = Path(arcname)
        desired_filename = arc_path.name
        prefix = str(arc_path.parent) + "/" if arc_path.parent != Path() else ""

        # Create a temporary directory with a file that has the desired filename.
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / desired_filename

        try:
            # Write data to temp file
            temp_path.write_bytes(data)

            # Track temp directory for later cleanup.
            self._temp_dirs.append(temp_dir)

            # Add the temp file path and prefix.
            self.file_paths.append(str(temp_path))
            self.prefixes.append(prefix)

        except Exception:
            # Clean up temp dir if something goes wrong.
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    def write(self) -> None:
        """Write all collected files to ZIP (call this after adding all files)."""
        if not self.file_paths:
            return

        try:
            pyminizip.compress_multiple(
                self.file_paths,
                self.prefixes,
                self.output_zip,
                self.password,
                self.compression_level,
            )
        finally:
            # Clean up temporary directories created by add_str.
            for temp_dir in self._temp_dirs:
                shutil.rmtree(temp_dir, ignore_errors=True)
            self._temp_dirs.clear()

    def __enter__(self):  # noqa: ANN204
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):  # noqa: ANN001, ANN204
        """Write ZIP on context exit."""
        if exc_type is None:  # Only write if no exception
            self.write()
        else:
            # Clean up temp dirs even on exception.
            for temp_dir in self._temp_dirs:
                shutil.rmtree(temp_dir, ignore_errors=True)
            self._temp_dirs.clear()
