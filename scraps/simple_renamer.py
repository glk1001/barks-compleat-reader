from pathlib import Path

# ext = ".jpg"
# ext = ".png"
# ext = ".json"
ext= ".png"

print(f'CWD: "{Path.cwd()}", ext: "{ext}"')

for srce_file in Path.cwd().glob('*' + ext):
    # file_str = str(srce_file).replace("final", "prelim")
    # dest_file = Path(file_str)
    renamed_file = srce_file.with_suffix(".svg.png")
    dest_file = renamed_file

#for i in range(7,31):
    # srce_file = Path(f"{i:03d}-gemini-final-groups-paddleocr{ext}")
    # if not srce_file.is_file():
    #     raise FileNotFoundError(srce_file)
    # dest_file = Path(f"{i:03d}-paddleocr-gemini-final-groups{ext}")

    srce_file.rename(dest_file)
    print(f'Rename: "{srce_file}" -> "{dest_file}"')
