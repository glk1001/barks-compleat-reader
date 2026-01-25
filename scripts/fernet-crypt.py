# ruff: noqa: T201

import os
from pathlib import Path

import typer
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env.runtime")

PANEL_KEY = os.environ["BARKS_ZIPS_KEY"]
FERNET = Fernet(PANEL_KEY)


def crypt_file(srce_file: Path, dest_file: Path, crypt_flag: bool) -> None:
    try:
        with srce_file.open("rb") as file:
            data = file.read()

        dest_data = FERNET.encrypt(data) if crypt_flag else FERNET.decrypt(data)

        with dest_file.open("wb") as file:
            file.write(dest_data)

        crypt_type = "encrypted" if crypt_flag else "decrypted"

        print(f"File '{srce_file}' successfully {crypt_type} to '{dest_file}'.")

    except FileNotFoundError:
        print("Error: One of the specified files was not found.")
    except Exception as e:  # noqa: BLE001
        print(f"An error occurred during decryption: {e}")


app = typer.Typer()


@app.command(help="Encrypt a source to a dest file")
def encrypt(srce: Path, dest: Path) -> None:
    crypt_file(srce, dest, crypt_flag=True)


@app.command(help="Decrypt a source to a dest file")
def decrypt(srce: Path, dest: Path) -> None:
    crypt_file(srce, dest, crypt_flag=False)


if __name__ == "__main__":
    app()
