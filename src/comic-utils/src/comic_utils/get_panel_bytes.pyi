# Type stub for the gitignored, Cython-compiled get_panel_bytes module.
# The real implementation ships as a .so/.pyd built from an encrypted
# .pyx.template (see scripts/cythonize-panel-module.sh); the .py/.pyx/.so
# artifacts are all gitignored, so ty can't resolve the import from source.
# This .pyi gives ty a signature to check against without shadowing the
# compiled module at runtime (Python ignores .pyi files at import time).
# At runtime, fork PRs without the decryption key fall back to a generated
# stub .py (see .github/workflows/build.yml); real builds use the .so/.pyd.

def get_decrypted_bytes(data: bytes) -> bytes: ...
