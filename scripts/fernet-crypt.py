# ruff: noqa: T201

import argparse
import os
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env.runtime")

PANEL_KEY = os.environ["BARKS_ZIPS_KEY"]
FERNET = Fernet(PANEL_KEY)


def crypt_file(srce_file: Path, dest_file: Path, encrypt: bool) -> None:
    try:
        with srce_file.open("rb") as file:
            data = file.read()

        dest_data = FERNET.encrypt(data) if encrypt else FERNET.decrypt(data)

        with dest_file.open("wb") as file:
            file.write(dest_data)

        print(f"File '{srce_file}' successfully crypted to '{dest_file}'.")

    except FileNotFoundError:
        print("Error: One of the specified files was not found.")
    except Exception as e:  # noqa: BLE001
        print(f"An error occurred during decryption: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encrypt and decrypt files using Fernet.")
    parser.add_argument("action", choices=["encrypt", "decrypt"], help="Action to perform.")
    parser.add_argument("--srce", help="Path to the file to encrypt or decrypt.", required=True)
    parser.add_argument("--dest", help="Path of output file.", required=True)

    args = parser.parse_args()

    crypt_file(Path(args.srce), Path(args.dest), encrypt=args.action == "encrypt")
