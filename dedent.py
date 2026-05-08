#!/usr/bin/env python3
"""
Recursively left-align files in a directory by removing common leading whitespace.
Files already left-aligned (i.e., at least one non-empty line starts at column 0)
are left untouched.
"""

import argparse
import os
import sys
from pathlib import Path


# Directory names that should never be descended into.
SKIP_DIRS = frozenset({
    # VCS
    ".git", ".hg", ".svn", ".bzr", "_darcs", "CVS",
    # Python
    "__pycache__", ".venv", "venv", ".tox", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", ".pyc_cache", ".eggs",
    # JS / Node
    "node_modules", ".yarn", ".pnpm-store", ".next", ".nuxt",
    # Rust / build
    "target", "build", "dist", "out", ".cargo",
    # Editors / IDEs
    ".idea", ".vscode", ".vs", ".cache",
    # Misc
    ".direnv", ".terraform", ".gradle",
})


def compute_common_indent(text: str) -> int:
    """Return the length of the longest common leading whitespace prefix
    across all non-empty lines. Returns 0 if any non-empty line has no indent."""
    lines = text.splitlines()
    common = None
    for line in lines:
        if not line.strip():
            continue
        stripped = line.lstrip(" \t")
        indent = line[: len(line) - len(stripped)]
        if common is None:
            common = indent
        else:
            i = 0
            limit = min(len(common), len(indent))
            while i < limit and common[i] == indent[i]:
                i += 1
            common = common[:i]
            if not common:
                return 0
    return len(common) if common else 0


def dedent_text(text: str, n: int) -> str:
    """Remove the first n leading whitespace chars from each line."""
    out_lines = []
    for line in text.splitlines(keepends=True):
        stripped_line = line.rstrip("\r\n")
        ending = line[len(stripped_line):]
        if stripped_line.strip() == "":
            out_lines.append(ending)
        else:
            prefix = stripped_line[:n]
            if all(c in " \t" for c in prefix):
                out_lines.append(stripped_line[n:] + ending)
            else:
                out_lines.append(stripped_line + ending)
    return "".join(out_lines)


def process_file(path: Path, dry_run: bool = False) -> bool:
    try:
        original = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        print(f"skip {path}: {e}", file=sys.stderr)
        return False

    n = compute_common_indent(original)
    if n == 0:
        return False

    new_text = dedent_text(original, n)
    if new_text == original:
        return False

    if dry_run:
        print(f"would dedent {path} by {n} chars")
    else:
        path.write_text(new_text, encoding="utf-8")
        print(f"dedented {path} by {n} chars")
    return True


def main():
    parser = argparse.ArgumentParser(description="Recursively left-align files.")
    parser.add_argument("directory", type=Path, help="Root directory to walk")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="Show what would change without writing")
    parser.add_argument("--ext", action="append", default=None,
                        help="Only process files with this extension "
                             "(may be given multiple times, e.g. --ext .glsl).")
    parser.add_argument("--follow-symlinks", action="store_true",
                        help="Follow symlinks when walking the directory")
    parser.add_argument("--include-hidden", action="store_true",
                        help="Don't skip dotfiles/dotdirs (still skips known-bad dirs "
                             "like .git unless --no-skip-dirs is also given)")
    parser.add_argument("--no-skip-dirs", action="store_true",
                        help="Disable the built-in skip list (.git, node_modules, etc.). "
                             "Dangerous; use with care.")
    args = parser.parse_args()

    root: Path = args.directory
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        sys.exit(1)

    exts = None
    if args.ext:
        exts = {e if e.startswith(".") else "." + e for e in args.ext}

    changed = 0
    total = 0
    skipped_dirs = 0

    for dirpath, dirnames, filenames in os.walk(root, followlinks=args.follow_symlinks):
        # Prune dirnames in place so os.walk doesn't descend into them.
        pruned = []
        for d in dirnames:
            if not args.no_skip_dirs and d in SKIP_DIRS:
                skipped_dirs += 1
                continue
            if not args.include_hidden and d.startswith("."):
                skipped_dirs += 1
                continue
            pruned.append(d)
        dirnames[:] = pruned

        for name in filenames:
            if not args.include_hidden and name.startswith("."):
                continue
            p = Path(dirpath) / name
            if exts is not None and p.suffix not in exts:
                continue
            if not p.is_file() or p.is_symlink():
                continue
            total += 1
            if process_file(p, dry_run=args.dry_run):
                changed += 1

    verb = "would change" if args.dry_run else "changed"
    print(f"{verb} {changed} of {total} file(s); skipped {skipped_dirs} dir(s)")


if __name__ == "__main__":
    main()
