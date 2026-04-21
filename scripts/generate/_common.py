"""Shared utilities for the DSL generator scripts."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_DIR = (
    REPO_ROOT
    / "plugins"
    / "swagger-contract-testing"
    / "skills"
    / "pactflow"
    / "references"
)


def clone_shallow(repo_url: str, ref: str, dest: Path) -> None:
    """Shallow-clone *repo_url* at *ref* into *dest*."""
    subprocess.run(
        ["git", "clone", "--depth=1", f"--branch={ref}", repo_url, str(dest)],
        check=True,
    )


def run_main(
    build_doc: Callable[[Path], str],
    dest_path: Path,
    repo_url: str,
    repo_dirname: str,
    env_var: str,
    default_ref: str,
    description: str | None = None,
) -> None:
    """Standard CLI entrypoint for single-output DSL generators."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--ref",
        default=os.environ.get(env_var, default_ref),
        help=f"Branch or tag to clone (default: ${env_var} or {default_ref!r})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=dest_path,
        help=f"Output path (default: {dest_path})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if the output file would change (CI mode)",
    )
    parser.add_argument(
        "--local-repo",
        type=Path,
        default=None,
        metavar="PATH",
        help="Use a local checkout instead of cloning (for development)",
    )
    args = parser.parse_args()

    if args.local_repo:
        repo = args.local_repo.resolve()
        doc = build_doc(repo)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / repo_dirname
            clone_shallow(repo_url, args.ref, repo)
            doc = build_doc(repo)

    if args.check:
        existing = args.output.read_text() if args.output.exists() else ""
        if doc != existing:
            print(
                f"[check] {args.output} is out of date — run the generator to update",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"[check] {args.output} is up to date")
        return

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(doc)
    print(f"Wrote {args.output}")
