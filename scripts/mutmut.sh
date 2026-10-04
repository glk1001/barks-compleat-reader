#!/bin/bash
# Mutation testing for barks_reader (or, with --package fantagraphics, the
# barks_fantagraphics search modules) with mutmut.
#
# Why a wrapper (mutmut can't just run at the repo root):
#   1. Layout — mutmut's source-shadowing assumes a repo-root src/ layout, but the
#      package lives at src/barks-reader/src/barks_reader and is editable-installed.
#      Running from src/barks-reader makes the layout mutmut expects, so its copy in
#      mutants/ shadows the editable install and the tests import the MUTATED code.
#   2. Tests — mutmut runs the test suite inside its mutants/ sandbox, where the Kivy
#      UI tests don't behave (global window/app state), so a single UI test failure
#      aborts the whole run. We therefore select only the Kivy-free unit tests as the
#      baseline. This list is computed fresh each run, so new pure tests join
#      automatically and no brittle hand-maintained list can drift.
#
# The mutmut config is written to a throwaway setup.cfg in the package's folder
# (gitignored); keeping [tool.mutmut] out of pyproject.toml keeps that file clean.
#
# --package fantagraphics (first argument) runs the same way in src/barks-fantagraphics:
# its own src/ layout, all of its tests (none use Kivy), and by default the search
# modules - the query parser and evaluator, tag queries, terms, filters, results, the
# facade, title search and the Whoosh engine. A glob or --changed then works as below,
# with */barks_fantagraphics/ in place of */core/.
#
# Usage:
#   bash scripts/mutmut.sh                             # mutate all of core/
#   bash scripts/mutmut.sh '*/core/navigation/*'      # scope to a subpackage
#   bash scripts/mutmut.sh '*/core/navigation/navigation_model.py'   # one module
#   bash scripts/mutmut.sh --changed                   # only core/ modules you have touched
#   bash scripts/mutmut.sh --changed HEAD~3            # ...plus everything since a ref
#   bash scripts/mutmut.sh --package fantagraphics      # the search modules
#   bash scripts/mutmut.sh --package fantagraphics '*/barks_fantagraphics/tag_query.py'
#
# --changed is the everyday mode: a full core/ sweep is ~6000 mutants and many
# minutes, but one module is a minute or two, which is fast enough to run while the
# code is still fresh in your head. With no ref it scopes to your working tree
# (staged, unstaged and untracked); pass a ref to also include commits since then.
#
# Inspect afterwards (from the package's folder, src/barks-reader or src/barks-fantagraphics):
#   uv run mutmut results | grep survived
#   uv run mutmut show <mutant-name>
# Five traps that make survivor counts lie (property tests in classes, functools.cache,
# cleared environments, module-scoped fixtures, decorated classes and functions, which
# get no mutants at all): see docs/mutation-testing.md first.

set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)

package="reader"
if [[ "${1:-}" == "--package" ]]; then
    package="${2:-}"
    shift 2 || true
fi
case "${package}" in
    reader)
        package_dir="src/barks-reader"
        source_path="src/barks_reader"
        core_rel="src/barks-reader/src/barks_reader/core"  # the modules mutated
        tests_rel="src/barks-reader/tests/unit"
        glob_prefix="*/core/"
        default_globs="*/core/*"
        module_prefix='barks_reader\.core\.'  # stripped from mutant names in the summary
        also_copy=""
        ;;
    fantagraphics)
        package_dir="src/barks-fantagraphics"
        source_path="src/barks_fantagraphics"
        core_rel="src/barks-fantagraphics/src/barks_fantagraphics"
        tests_rel="src/barks-fantagraphics/tests"
        glob_prefix="*/barks_fantagraphics/"
        default_globs=""
        for module in search_query search_evaluate tag_query search_terms search_filters \
            search_results comic_search title_search whoosh_search_engine; do
            default_globs+="${default_globs:+$'\n'}*/barks_fantagraphics/${module}.py"
        done
        module_prefix='barks_fantagraphics\.'
        # comics_consts asserts its data folder exists, beside src/ in the source tree;
        # the sandbox has none unless mutmut copies it to mutants/data.
        also_copy="data"
        ;;
    *)
        echo "mutmut: unknown --package '${package}' (reader or fantagraphics)" >&2
        exit 2
        ;;
esac

# Core modules touched in the working tree, plus (if a base ref is given) any touched
# by commits since it. Deleted files are dropped - there is nothing left to mutate.
#
# Changed *tests* count too, mapped back via the tests/unit/test_<module>.py naming
# convention. Hardening a test without touching its module is the single most common
# reason to run mutmut at all, and scoping on source changes alone would find nothing
# to do in exactly that case.
changed_core_globs() {
    local base="${1:-}"
    {
        git -C "${repo_root}" diff --name-only HEAD -- "${core_rel}" "${tests_rel}"
        git -C "${repo_root}" ls-files --others --exclude-standard -- "${core_rel}" "${tests_rel}"
        if [[ -n "${base}" ]]; then
            git -C "${repo_root}" diff --name-only "${base}" -- "${core_rel}" "${tests_rel}"
        fi
    } | sort -u | while read -r path; do
        [[ -n "${path}" && "${path}" == *.py ]] || continue
        case "${path}" in
            "${core_rel}"/*)
                [[ -f "${repo_root}/${path}" ]] || continue
                printf '%s%s\n' "${glob_prefix}" "${path#"${core_rel}"/}"
                ;;
            "${tests_rel}"/test_*.py)
                local module="${path##*/test_}"
                # Only a top-level core module; nested ones have no naming convention.
                # An if, not "&&": under set -e a false test as the loop's last command
                # made the whole pipeline fail, and the script exited before mutating
                # anything - silently, since the failure was inside "globs=$(...)".
                if [[ -f "${repo_root}/${core_rel}/${module}" ]]; then
                    printf '%s%s\n' "${glob_prefix}" "${module}"
                fi
                ;;
        esac
    done | sort -u
}

if [[ "${1:-}" == "--changed" ]]; then
    shift
    base=""
    if [[ $# -gt 0 && "$1" != -* ]]; then
        base="$1"
        shift
    fi
    globs=$(changed_core_globs "${base}")
    if [[ -z "${globs}" ]]; then
        echo "mutmut: no changed files under ${core_rel} — nothing to mutate."
        echo "        (pass a base ref, e.g. 'bash scripts/mutmut.sh --changed HEAD~1')"
        exit 0
    fi
    echo "mutmut: --changed selected $(printf '%s\n' "${globs}" | grep -c .) module(s):"
    printf '  %s\n' ${globs}
    # configparser reads a multi-line value only when the continuation lines are
    # indented, so every glob after the first gets four spaces.
    only_mutate=$(printf '%s\n' "${globs}" | sed -e '2,$s/^/    /')
else
    only_mutate="${1:-$(printf '%s\n' "${default_globs}" | sed -e '2,$s/^/    /')}"
    [[ $# -gt 0 ]] && shift || true
fi

cd "${repo_root}/${package_dir}"

# Kivy-free unit tests only — UI tests fail in mutmut's sandbox and abort the run.
# Two more are left out, since mutmut copies the tests under mutants/ and runs
# them from there: the first-run installer's test (that module, not in core/ and
# never mutated, resolves the executable's directory at import time, which
# asserts in the sandbox), and the GUI harness's tests (they put scripts/ and
# tests/gui on sys.path relative to their own file, which is elsewhere in the
# sandbox). Either takes the whole baseline down before a single mutant runs.
tests_dir="${tests_rel#"${package_dir}"/}"
selection=$(cd "${tests_dir}" && for f in test_*.py; do
    grep -qE '^(import kivy|from kivy|import barks_reader\.ui|from barks_reader\.ui|from barks_reader import first_run_installer|from barks_reader\.first_run_installer|import gui_driver|from barks_gui)' "$f" \
        || printf '    %s/%s\n' "${tests_dir}" "$f"
done)

cat > setup.cfg <<EOF
# Generated by scripts/mutmut.sh at runtime — do not edit or commit (gitignored).
[mutmut]
source_paths = ${source_path}
only_mutate = ${only_mutate}
${also_copy:+also_copy = ${also_copy}
}pytest_add_cli_args = --import-mode=importlib
pytest_add_cli_args_test_selection =
${selection}
EOF

echo "mutmut: mutating against $(echo "${selection}" | grep -c .) Kivy-free test files"
rm -rf mutants
# mutmut exits non-zero when mutants survive, so its status says nothing; what it
# prints does. When the test run itself breaks (a collection error, no tests), it
# tests no mutant, and a summary of zero survivors would read as a clean slice.
run_log="$(mktemp)"
uv run mutmut run "$@" 2>&1 | tee "${run_log}" || true
if grep -qE '^failed to collect stats|^Stopping early, because' "${run_log}"; then
    rm -f "${run_log}"
    echo "mutmut: the test run failed, so no mutant was tested (see above)" >&2
    exit 1
fi
rm -f "${run_log}"

echo
echo "==== survivors by module ===="
# mutmut names mutants <module>.x_<func>__mutmut_N for plain functions and
# <module>.xǁ<Class>ǁ<method>__mutmut_N for methods. Strip from whichever marker
# appears so BOTH forms collapse to the module name - an earlier version only
# handled the ǁ form, which silently under-reported this summary.
# grep finds nothing in a slice with no survivors; under pipefail that is not a failure.
survivors=$(uv run mutmut results 2>/dev/null | { grep ': survived' || true; })
if [[ -n "${survivors}" ]]; then
    printf '%s\n' "${survivors}" | sed -E "s/.*${module_prefix}//; s/\\.(x_|xǁ).*//" \
        | sort | uniq -c | sort -rn
fi
echo "  total survivors: $(printf '%s\n' "${survivors}" | grep -c .)"
