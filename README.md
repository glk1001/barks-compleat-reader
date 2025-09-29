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
- **Powerful Search**: Quickly find titles by name or stories by specific tags using the integrated search boxes.
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

- **Python**: 3.12 or newer.
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

## Building a Standalone Executable Using Pyinstaller
1. Install pyinstaller:
    ```
    uv add --dev pyinstaller
    ```
1. Activate the python virtual environment:
    ```
   source .venv/bin/activate
   
   (source .venv/Scripts/activate on Windows)
    ```
1. Run the pyinstaller build command:
    ```
    pyinstaller -y --clean --workpath /tmp/barks-reader-build --distpath /tmp/barks-reader-dist main-onefile.spec
    ```
1. The standalone one-file executable will be at '/tmp/barks-reader-dist/main'.
   Rename the executable:
    ```
    mv /tmp/barks-reader-dist/main ~/.local/bin/barks-reader
    ```

## License

This project is licensed under the GPL License.
