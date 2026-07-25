# Vulture whitelist — false positives that vulture cannot resolve on its own.
#
# Vulture parses this file and treats each bare name as "used", suppressing the
# corresponding report. It is intentionally coarse (matching is by name), which is
# acceptable here because ruff still guards the same names via F401/F841/ARG.
#
# Regenerate the raw list with:
#     uv run vulture src/*/src --min-confidence 80 --make-whitelist
# then fold new *genuine* false positives into the grouped sections below.

# --- Protocol / interface method parameters -------------------------------------
# Parameters on `...`-bodied Protocol stubs in core/reader_settings.py. They define
# the interface contract, so the names must stay even though no body consumes them.
option    # ConfigParser.set(section, option, value)
defaults  # BuildableConfigParser.setdefaults(section, defaults)

# --- Kivy lifecycle override parameters -----------------------------------------
# `on_kv_post(self, base_widget)` — Kivy passes base_widget positionally; the
# override keeps the parameter to match the framework signature (already # noqa: ARG002).
base_widget  # goto_title_overlay.py / settings_fix.py on_kv_post

# --- Kivy graphics imports referenced indirectly --------------------------------
# `from kivy.graphics import Canvas, ...` — ruff's F401 confirms these are used
# (via canvas instructions / annotations); vulture's static pass misses the usage.
Canvas  # main_index_screen.py / speech_index_screen.py
