"""
Password-protected ZIP creation and reading example
Requires: pip install pyzipper
"""

import pyzipper
import os
from pathlib import Path

# Password configuration
ZIP_PASSWORD = b"my_secret_password"


def create_protected_zip(files, output_zip="data.zip", password=ZIP_PASSWORD):
    """
    Create a password-protected ZIP file.

    Args:
        files: List of file paths to include
        output_zip: Output ZIP filename
        password: Password as bytes
    """
    with pyzipper.AESZipFile(
        output_zip, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES
    ) as zf:
        zf.setpassword(password)

        for file_path in files:
            if os.path.exists(file_path):
                # Add file with its basename (not full path)
                zf.write(file_path, arcname=os.path.basename(file_path))
                print(f"Added: {file_path}")
            else:
                print(f"Warning: {file_path} not found, skipping")

    print(f"\nCreated protected ZIP: {output_zip}")


def read_protected_zip(zip_path="data.zip", output_dir="extracted", password=ZIP_PASSWORD):
    """
    Read and extract a password-protected ZIP file.

    Args:
        zip_path: Path to ZIP file
        output_dir: Directory to extract to
        password: Password as bytes
    """
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(exist_ok=True)

    with pyzipper.AESZipFile(zip_path, "r") as zf:
        zf.setpassword(password)

        # List contents
        print(f"Contents of {zip_path}:")
        for name in zf.namelist():
            info = zf.getinfo(name)
            print(f"  {name} ({info.file_size} bytes)")

        # Extract all
        zf.extractall(output_dir)
        print(f"\nExtracted to: {output_dir}")


def read_specific_file(zip_path="data.zip", filename="data.txt", password=ZIP_PASSWORD):
    """
    Read a specific file from password-protected ZIP without extracting.

    Args:
        zip_path: Path to ZIP file
        filename: Name of file to read
        password: Password as bytes

    Returns:
        File content as bytes
    """
    with pyzipper.AESZipFile(zip_path, "r") as zf:
        zf.setpassword(password)

        if filename in zf.namelist():
            content = zf.read(filename)
            print(f"Read {filename}: {len(content)} bytes")
            return content
        else:
            print(f"File {filename} not found in ZIP")
            return None


# Example usage
if __name__ == "__main__":
    # Example 1: Create some test files
    test_files = ["file1.txt", "file2.txt", "file3.txt"]
    for i, fname in enumerate(test_files, 1):
        with open(fname, "w") as f:
            f.write(f"This is test file {i}\n")

    # Example 2: Create protected ZIP
    print("=" * 50)
    print("CREATING PASSWORD-PROTECTED ZIP")
    print("=" * 50)
    create_protected_zip(test_files, "example.zip")

    # Example 3: Read protected ZIP
    print("\n" + "=" * 50)
    print("READING PASSWORD-PROTECTED ZIP")
    print("=" * 50)
    read_protected_zip("example.zip", "extracted_files")

    # Example 4: Read specific file without extracting
    print("\n" + "=" * 50)
    print("READING SPECIFIC FILE FROM ZIP")
    print("=" * 50)
    content = read_specific_file("example.zip", "file1.txt")
    if content:
        print(f"Content: {content.decode()}")

    # Cleanup test files
    for fname in test_files:
        os.remove(fname)
    print("\nTest files cleaned up")
