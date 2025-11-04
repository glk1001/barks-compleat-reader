import io
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from tkinter.font import Font

from PIL import Image


def show_error(
    message: str, bgnd_image_file: Path | None, window_title: str = "Barks Reader Error"
) -> None:
    show_message(message, "An Unexpected Error Has Occurred", bgnd_image_file, window_title)


def show_message(
    message: str, heading: str, bgnd_image_file: Path | None, window_title: str
) -> None:
    root = tk.Tk()
    root.withdraw()

    _show_custom_message(
        root,
        window_title,
        heading,
        message,
        1000,
        800,
        bgnd_image_file,
    )
    root.mainloop()


def _show_custom_message(
    root: tk.Tk,
    title: str,
    heading: str,
    message: str,
    width: int,
    height: int,
    bgnd_image_file: Path | None,
) -> None:
    msg_window = tk.Toplevel(root)
    msg_window.title(title)

    # Withdraw window before positioning
    msg_window.withdraw()

    msg_window.geometry(f"{width}x{height}")
    msg_window.resizable(width=False, height=False)

    # Calculate canvas height (subtract space for button)
    canvas_height = height - 100  # Leave space for the button
    canvas_actual_width = width - 20

    canvas_text_width = canvas_actual_width - 100
    title_font = Font(family="Helvetica", size=26, weight="bold")
    text_font = Font(family="Helvetica", size=18, weight="bold")
    button_font = Font(family="Helvetica", size=20, weight="bold")
    opacity = 0.2  # 0.0 = fully transparent, 1.0 = fully opaque

    # Create a canvas that fills the content area without padding
    canvas = tk.Canvas(msg_window, width=width - 20, height=canvas_height, highlightthickness=0)
    canvas.pack(padx=10, pady=(10, 0), fill="both", expand=False)

    if bgnd_image_file:
        image_width, image_height, photo_image = _get_scaled_icon_image(
            canvas_actual_width, canvas_height, bgnd_image_file, opacity
        )

        # Store reference to prevent garbage collection.
        msg_window.photo_image = photo_image  # ty: ignore[unresolved-attribute]

        # Center the image on the canvas.
        x_offset = (canvas_actual_width - image_width) // 2
        y_offset = (canvas_height - image_height) // 2

        # Draw the resized icon on the canvas.
        canvas.create_image(x_offset, y_offset, image=photo_image, anchor="nw")

    # Use the actual canvas dimensions for centering text.
    canvas_center_x = canvas_actual_width // 2
    canvas_center_y = canvas_height // 2

    # Draw the title text at the top with larger font.
    title_ypos = 40
    canvas.create_text(
        canvas_center_x,
        title_ypos,
        text=heading,
        anchor="n",
        width=canvas_text_width,
        font=title_font,
        fill="red",
        justify="center",  # Options: 'left', 'center', 'right'
    )

    # Draw the message text centered both horizontally and vertically.
    # Change justify to 'left' for left-aligned or 'right' for right-aligned.

    canvas.create_text(
        canvas_center_x,
        canvas_center_y,
        text=message,
        anchor="center",
        width=canvas_text_width,
        font=text_font,
        fill="black",
        justify="left",  # Options: 'left', 'center', 'right'
    )

    # Function to close both windows.
    def close_dialog() -> None:
        msg_window.destroy()
        root.quit()

    # Create a bigger OK button with custom styling.
    style = ttk.Style()
    style.configure("Big.TButton", font=button_font, foreground="blue")

    ok_button = ttk.Button(
        msg_window, text="OK", command=close_dialog, style="Big.TButton", width=3
    )
    ok_button.pack(
        side="bottom", padx=0, ipadx=5, pady=18, ipady=15
    )  # ipady adds internal padding vertically

    # Handle window close button (X).
    msg_window.protocol("WM_DELETE_WINDOW", close_dialog)

    # Update to get proper dimensions.
    msg_window.update_idletasks()

    # Center the window on the screen.
    screen_width = msg_window.winfo_screenwidth()
    screen_height = msg_window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    msg_window.geometry(f"{width}x{height}+{x}+{y}")

    # Now show the window.
    msg_window.deiconify()


def _get_scaled_icon_image(
    canvas_actual_width: int, canvas_height: int, icon_file: Path, opacity: float
) -> tuple[int, int, tk.PhotoImage]:
    pil_image = Image.open(str(icon_file))

    # Convert to RGBA if not already.
    if pil_image.mode != "RGBA":
        pil_image = pil_image.convert("RGBA")

    # Get original image dimensions.
    img_width, img_height = pil_image.size

    # Calculate scaling to cover the canvas while maintaining aspect ratio.
    scale_x = canvas_actual_width / img_width
    scale_y = canvas_height / img_height
    scale = max(scale_x, scale_y)  # Use max to cover (will crop if needed)

    # Calculate new dimensions.
    new_width = int(img_width * scale)
    new_height = int(img_height * scale)

    # Resize the image using PIL for smooth scaling.
    resized_pil = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Reduce opacity by adjusting the alpha channel.
    alpha = resized_pil.split()[3]  # Get the alpha channel
    alpha = alpha.point(lambda p: int(p * opacity))  # Reduce opacity
    resized_pil.putalpha(alpha)  # Put the modified alpha back

    # Convert PIL image to PNG bytes and then to PhotoImage.
    buffer = io.BytesIO()
    resized_pil.save(buffer, format="PNG")
    buffer.seek(0)

    # Create PhotoImage from the PNG data.
    photo_image = tk.PhotoImage(data=buffer.read())
    return new_width, new_height, photo_image


if __name__ == "__main__":
    msg = "line 1: with a bunch of text blah, blah, blah, blah, blah, blah, blah, blah, blah"
    msg += "line 2: with a bunch of text blah, blah, blah, blah, blah, blah, blah, blah, blah"
    msg += "line 3: with a bunch of text blah, blah, blah, blah, blah, blah, blah, blah, blah"
    msg += "line 4: with a bunch of text blah, blah, blah, blah, blah, blah, blah, blah, blah"
    msg += "line 5: with a bunch of text blah, blah, blah, blah, blah, blah, blah, blah, blah"

    background_image_file = (
        Path.home()
        / "Books/Carl Barks/Compleat Barks Disney Reader/Reader Files/Various/error-background.png"
    )
    # background_image_file = None  # noqa: ERA001
    show_error(msg, background_image_file)
