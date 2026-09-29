# Release process

The changelog is generated from Git history with [git-cliff](https://git-cliff.org/). Contributors do not maintain
`CHANGELOG.md` or add release-note files. User-visible commits should use Conventional Commit prefixes so they are
grouped correctly: `feat:`, `fix:`, `docs:`, `perf:`, `refactor:`, or `revert:`. Dependency updates use
`chore(deps):`; other chores, tests, build changes, and CI changes are omitted.

CI validates every commit in a pull request and every direct push to `main` with commitlint. Allowed types are defined
in [`commitlint.config.mjs`](../commitlint.config.mjs); generated merge commits are ignored by commitlint.

Install git-cliff before running the release commands. On macOS, use `brew install git-cliff`; other installation
options are documented in the [git-cliff installation guide](https://git-cliff.org/docs/installation/).

## Prepare a release

1. Confirm the release version and that `make check` passes on the release branch.
2. Preview the entries since the latest tag with `make changelog VERSION=1.3.0 DRY_RUN=1`.
3. Generate the complete changelog with `make changelog VERSION=1.3.0`. This rebuilds `CHANGELOG.md` from Git tags
   and commits.
4. Update the version in each affected plugin manifest.
5. Review and commit the changelog and version changes together.
6. Tag the commit as `v1.3.0` and publish the GitHub release using the generated changelog section as its notes.

The grouping and filtering rules live in [`cliff.toml`](../cliff.toml). Run `make changelog-check` to validate the
configuration without changing files.
