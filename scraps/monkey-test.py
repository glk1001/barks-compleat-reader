# --- CPI Database Monkey-Patch ---
# This block MUST run before any other code imports the 'cpi' package.
# It intercepts the import of 'cpi' to override the hardcoded path to 'cpi.db'.

import sys
import importlib.util
from importlib.abc import Loader, MetaPathFinder
from pathlib import Path
from types import ModuleType

# 1. Define the custom path where you want cpi.db to be located.
#    This should be a location your application has write access to.
CUSTOM_CPI_DB_PATH = Path("/home/greg/Prj/workdir/cpi.db")

# 2. Ensure the parent directory for your custom path exists.
CUSTOM_CPI_DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class CpiPatcher(MetaPathFinder):
    """
    An import hook that patches the 'cpi' module at load time using the
    modern 'find_spec' protocol.
    """

    def find_spec(self, fullname, path, target=None):  # noqa: ANN001, ANN201
        # This print statement is your test! If you see this, the hook is working.
        #        print(f"CpiPatcher.find_spec called for: {fullname}")

        if fullname == "cpi" or fullname == "cpi.models":
            print(f"Found cpi.")
            # We found the module we want to patch.
            # Temporarily remove our hook to avoid an infinite loop.
            sys.meta_path.remove(self)
            try:
                # Use the standard library to find the real module specification.
                spec = importlib.util.find_spec(fullname, path)
                if spec and spec.loader:
                    # If found, wrap the original loader with our custom one.
                    spec.loader = CpiLoader(spec.loader)
                return spec
            finally:
                # IMPORTANT: Always re-insert the hook.
                sys.meta_path.insert(0, self)
        return None


class CpiLoader(Loader):
    """
    A custom loader that executes the 'cpi' module and then patches it.
    """

    def __init__(self, original_loader: Loader):
        self.original_loader = original_loader

    def create_module(self, spec):  # noqa: ANN201
        # Let the original loader create the module object.
        return self.original_loader.create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        print(f"CpiLoader.exec_module called for '{module.__name__}'. Patching source...")

        # Get the source code of the original __init__.py
        source_code = self.original_loader.get_source(module.__name__)

        # Create a string representation of our custom path to inject.
        # Using repr() ensures it's a valid Python string literal.
        custom_path_str = repr(str(CUSTOM_CPI_DB_PATH))

        # Modify the source code to replace the original path definition
        # with our custom path. This is the core of the patch.
        modified_source = source_code.replace(
            'db_path = this_dir / "cpi.db"',  # Target for cpi/__init__.py
            f"db_path = Path({custom_path_str})  # Monkey-patched by BarksReader",
        )

        # Also patch the 'this_dir' variable in cpi/models.py
        # This ensures that if it constructs its own path, it uses our custom directory.
        custom_dir_str = repr(str(CUSTOM_CPI_DB_PATH.parent))
        modified_source = modified_source.replace(
            "this_dir = Path(__file__).parent.absolute()",
            f"this_dir = Path({custom_dir_str})  # Monkey-patched by BarksReader",
        )

        # Execute the modified source code in the context of the new module.
        # Now, all code within __init__.py, including the `db_path.exists()`
        # check and any subsequent database connections, will use our custom path.
        exec(modified_source, module.__dict__)

        # The patch is now complete. The module has been loaded using the correct path.
        print(f"Patch successful for '{module.__name__}'.")


# Insert our custom finder at the beginning of the meta_path list.
#    This ensures it runs before Python's default importers.
sys.meta_path.insert(0, CpiPatcher())

print("CPI patch hook installed. Now importing cpi...")
# --- End of CPI Database Monkey-Patch ---

import cpi

print(f"Monkey-patch applied. cpi.db_path is now set to: {cpi.db_path}")
