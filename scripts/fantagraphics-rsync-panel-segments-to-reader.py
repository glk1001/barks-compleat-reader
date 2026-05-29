import sysrsync
from barks_fantagraphics.comics_consts import FANTA_VOLUME_READER_PANEL_SEGMENTS_ROOT
from barks_fantagraphics.comics_database import ComicsDatabase

if __name__ == "__main__":
    comics_database = ComicsDatabase()

    panel_segments_srce_root = comics_database.get_fantagraphics_panel_segments_root_dir()
    panel_segments_reader_root = FANTA_VOLUME_READER_PANEL_SEGMENTS_ROOT

    sysrsync.run(
        source=str(panel_segments_srce_root),
        destination=str(panel_segments_reader_root),
        sync_source_contents=True,
        options=["--delete", "-L", "-avh"],
        strict=True,
        verbose=True,
    )
