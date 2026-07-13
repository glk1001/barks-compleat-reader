# The Compleat Barks Disney Reader

The Compleat Barks Disney Reader is a desktop application designed for browsing, searching, and reading the complete
collection of Carl Barks' Disney comics, specifically tailored for the Fantagraphics book series.

Built with the Kivy framework in Python, it provides a rich, cross-platform user experience with a focus on intuitive
navigation and a visually engaging interface.

## Features

- **Comprehensive Browsing**: Navigate the entire collection in multiple ways:
    - **Chronological**: View stories in order based on their original submission date.
    - **Series**: Browse by comic book series (e.g., *Walt Disney's Comics and Stories*, *Donald Duck*, *Uncle Scrooge*).
    - **Categories**: Explore stories grouped by tags, such as characters, themes, or story types.
- **Search**: Quickly find titles by name or stories by specific tags using the integrated search boxes.
- **Rich User Interface**: A dynamic 'TreeView' provides easy navigation, while the main view displays context-aware
  background art and information related to the selected comic or category.
- **Integrated Comic Reader**: A fullscreen, touch/click-friendly reader with intuitive page navigation (click
  left/right side of the screen) and a "go to page" dropdown for jumping directly to a specific page.
- **No Censorship**: Every attempt has been made to remove Disney and Fantagraphics censorship. This has been done
  using an override mechanism where censored pages in the original are overridden by fixed pages in the reader.
- **Smart Loading**: Asynchronously loads comic images in the background for a smooth, non-blocking user experience.
- **Customizable Viewing**: Supports optional override images for controversially restored or fixed pages, which can
  be toggled via a checkbox for specific titles.
- **Persistent State**: Remembers the last-read page for each comic and the last selected node on startup, allowing you
  to pick up right where you left off.

## Screenshots

*(Add screenshots of the main screen, the reader, and the settings panel here to showcase the application.)*

---

## Requirements

- **Python**: 3.13 or newer.
- **Fantagraphics Comic Archives**: You must have access to the digital versions of the Fantagraphics Carl Barks
  Library, typically as `.zip` or `.cbz` files.
- **Python Dependencies**: The required Python packages can be installed via `uv.`

## Installation and Setup

Follow these steps to get the application running on your local machine.

**1. Clone the required repository**

```bash
git clone https://github.com/glk1001/barks-compleat-reader.git
cd barks-compleat-reader
```

**2. Install Dependencies**

You need to use *uv* for package management and a Python virtual environment.

```uv
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install the required packages
uv sync
```

And install *just* to conveniently run commands.

```just
curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to ~/.local/bin
```

**3. Initial Run and Configuration**

The first time you run the application, it will create a configuration file. You will then need to configure the path to
your comic archives.

```
just reader
```
1. When the application opens, click the **Settings** icon in the action bar.
1. In the settings panel, locate the setting for the **"Fantagraphics Volumes Directory"**.
1. Set this to the absolute path of the folder containing your Fantagraphics comic book archive files (the `.zip` or
   `.cbz` files).
1. Close the settings panel and **restart the application**.

The application will now load the titles from your specified directory.

## Usage

- **Run the application**:
```
just reader
```
- **Navigation**: Use the `TreeView` on the left to browse the collection.
- **View Info**: Click on a title in the tree to see its related comic art, publication details, and other information
  in the main panel at the bottom.
- **Read a Comic**: In the bottom right corner of the main panel, click the highlighted comic inset image to open
  the comic book reader.

---

## Building a Standalone Executable Using Nuitka
1. Install the dependencies (Nuitka is a dev dependency):
    ```
    uv sync
    ```
1. Run the build command:
    ```
    bash scripts/build.sh
    ```
1. This will create a standalone executable in the repo root: a single-file binary on Linux
   ('barks-reader-linux') and Windows ('barks-reader-win.exe'), and a zipped `.app` bundle on
   macOS ('barks-reader-macos.zip' or 'barks-reader-macos-x64.zip', depending on architecture).

## Installing the Standalone App on macOS

Use 'barks-reader-macos.zip' on Apple Silicon Macs and 'barks-reader-macos-x64.zip' on Intel
Macs.

1. Unzip the download (double-click in Finder). You get `barks-reader-macos.app`. (Note: a zip
   downloaded from a GitHub Actions run's artifacts page is wrapped in an extra zip layer, so
   you may need to unzip twice; a file attached to a GitHub Release comes as-is.)
1. Put the `.app` in **its own folder** (e.g. `~/BarksReader/`), not straight into
   `/Applications`. The first-run installer looks for the data zips *beside the bundle*, and
   also writes its `config/` directory, install log, and data there.
1. Place `barks-reader-data-1.zip` and `barks-reader-data-2.zip` in that same folder, next to
   the `.app`.
1. Clear Gatekeeper — the app is unsigned, so a downloaded copy is quarantined and macOS will
   refuse to open it. Either:
    - try to open it once, then go to **System Settings → Privacy & Security**, scroll down
      and click **"Open Anyway"** (required on macOS 15+, where right-click → Open no longer
      works for unsigned apps); or
    - remove the quarantine flag in Terminal:
      ```
      xattr -dr com.apple.quarantine ~/BarksReader/barks-reader-macos.app
      ```
1. Launch the app. The first run unpacks the data zips, writes the config, and shows a
   success popup; subsequent launches go straight to the reader. If the install fails, the
   log is written beside the `.app` as `barks-reader-installer-<timestamp>.log`.

## Deployment
1. Goto 'Releases' on github (https://github.com/glk1001/barks-compleat-reader/releases/tag/v1.0.0) and edit the release:
    ```
    The Compleat Barks Disney Reader
    ```
1. Add the just built executable.
1. Update release
1. The updated release should be visible at https://glk1001.github.io/barks-compleat-reader/website/app.html

## License

This project is licensed under the Apache License.
