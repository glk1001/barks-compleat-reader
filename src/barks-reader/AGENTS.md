## Project Structure
All application-level code resides in the `src/` directory.

## Testing Instructions
*   Use `pytest` for all tests.
*   Tests should be placed in the `tests/unit` directory.
*   Run tests using the command: `uv run pytest`
*   Use pytest fixtures
*   Use Mock `patch.object` like:  
    `patch.object(image_file_getter, TitleImageFileGetter.__name__)`  
    **NOT**  
    `patch("barks_reader.core.image_file_getter.TitleImageFileGetter")`

## Code Style
*   Use modern Python 3.13+ syntax.
*   **Type hints are required on all function signatures**.
*   Use `str | None` for optional types, not `Optional[str]`.
*   All public functions must have Google-style docstrings.
*   Code formatting is handled by `ruff`.
*   Type checking is handled by `ty`.
