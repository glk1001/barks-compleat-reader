from pathlib import Path

from barks_reader.open_zip_archive import get_opened_zip_file  # ty: ignore[unresolved-import]

source_file = (
    Path.home() / "Books/Carl Barks/Compleat Barks Disney Reader/Reader Files/Barks Panels.zip"
)

archive = get_opened_zip_file(source_file)
extract_dir = "/tmp"  # noqa: S108
file_to_extract = "AI/A Campaign of Note/071-3-clean.jpg"

archive.extract(file_to_extract, extract_dir)
