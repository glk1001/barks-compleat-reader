echo Checking .kv '#: import' directives resolve:

# Whole-repo by nature: a .kv directive can be broken by a Python rename anywhere,
# not just in a changed .kv file, so there is nothing useful to scope to the diff.
echo
uv run scripts/check_kv_imports.py
