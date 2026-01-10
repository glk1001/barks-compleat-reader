import typer
from click import BadParameter

app = typer.Typer()


def func1(num: int) -> int:
    return num * num


def func2(num: int) -> int:
    return num * num * num


@app.command()
def main(name: str, num_sq: int = 0, num_cube: int = 0) -> None:
    if num_sq > 0 and num_cube > 0:
        raise typer.BadParameter("Options --num-sq and --num-cube are mutually exclusive.")

    num = func1(num_sq) if num_sq > 0 else func2(num_cube)

    print(f'Name: "{name}", num: {num}.')


if __name__ == "__main__":
    app()
