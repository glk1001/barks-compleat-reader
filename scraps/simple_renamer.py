from pathlib import Path

# ext = ".jpg"
ext = ".png"
# ext = ".json"
# ext= ".svg"
# ext= ".svg.png"
for srce_dir in Path.cwd().iterdir():
    if not srce_dir.is_dir():
        continue
    for srce_file in srce_dir.iterdir():
        if "final" not in srce_file.name:
            continue
        file_str = str(srce_file).replace("final-text", "prelim")
        dest_file = Path(file_str)
    #for i in range(7,31):
        # srce_file = Path(f"{i:03d}-gemini-final-groups-paddleocr{ext}")
        # if not srce_file.is_file():
        #     raise FileNotFoundError(srce_file)
        # dest_file = Path(f"{i:03d}-paddleocr-gemini-final-groups{ext}")

        srce_file.rename(dest_file)
        print(f'Rename: "{srce_file}" -> "{dest_file}"')
