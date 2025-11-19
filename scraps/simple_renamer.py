from pathlib import Path

# ext = ".jpg"
#ext = ".png"
ext = ".json"
# ext= ".svg"
# ext= ".svg.png"
for srce_file in Path.cwd().iterdir():
    file_str = srce_file.stem
    if file_str.startswith("batch-job-details-"):
        dest_file = Path(file_str[len("batch-job-details-"):] + "-batch-job-details.json")
    elif file_str.startswith("batch-requests-with-image-"):
        dest_file = Path(file_str[len("batch-requests-with-image-"):] + "-batch-requests-with-image.json")
    else:
        print(f"Skipping: {file_str}")
        continue

#for i in range(7,31):
    # srce_file = Path(f"{i:03d}-gemini-final-groups-paddleocr{ext}")
    # if not srce_file.is_file():
    #     raise FileNotFoundError(srce_file)
    # dest_file = Path(f"{i:03d}-paddleocr-gemini-final-groups{ext}")

    srce_file.rename(dest_file)
    print(f'Rename: "{srce_file}" -> "{dest_file}"')
