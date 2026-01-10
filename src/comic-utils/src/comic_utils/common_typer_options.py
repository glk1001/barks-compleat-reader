from typing import Annotated

import typer

LogLevelArg = Annotated[str, typer.Option("--log-level", help="Log level")]
PagesArg = Annotated[str, typer.Option("--page", help="Comic page numbers")]
TitleArg = Annotated[str, typer.Option("--title", help="Comic title")]
VolumesArg = Annotated[str, typer.Option("--volume", help="Fanta volume list")]
