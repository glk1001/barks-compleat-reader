from pathlib import Path

# ext = ".jpg"
ext = ".png"
# ext = ".json"
# ext= ".svg"
# ext= ".svg.png"
for i in range(250):
    srce_file = Path(f"{249 - i:03d}{ext}")
    if not srce_file.is_file():
        continue
        # raise FileNotFoundError(srce_file)
    dest_file = Path(f"{249 - i + 1:03d}{ext}")

    srce_file.rename(dest_file)
    print(f'Rename: "{srce_file}" -> "{dest_file}"')
