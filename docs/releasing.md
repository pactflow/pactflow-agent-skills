# Release process

The changelog is generated from Git history with [git-cliff](https://git-cliff.org/). Contributors do not maintain
`CHANGELOG.md` or add release-note files. User-visible commits should use Conventional Commit prefixes so they are
grouped correctly: `feat:`, `fix:`, `docs:`, `perf:`, `refactor:`, or `revert:`. Dependency updates use
`chore(deps):`; other chores, tests, build changes, and CI changes are omitted.

CI validates every commit in a pull request and every direct push to `main` with commitlint. Allowed types are defined
in [`commitlint.config.mjs`](../commitlint.config.mjs); generated merge commits are ignored by commitlint.

Install git-cliff before running the release commands. On macOS, use `brew install git-cliff`; other installation
options are documented in the [git-cliff installation guide](https://git-cliff.org/docs/installation/).

Use semantic versioning for plugin releases:

- **Major:** incompatible changes to skill invocation, plugin configuration, or documented behavior.
- **Minor:** backward-compatible capabilities, skills, agents, or workflow additions.
- **Patch:** backward-compatible fixes and documentation corrections.

## Prepare a release

1. Confirm the release version and that `make check` passes on the release branch.
2. Preview the entries since the latest tag with `make changelog VERSION=1.3.0 DRY_RUN=1`.
3. Generate the complete changelog with `make changelog VERSION=1.3.0`. This rebuilds `CHANGELOG.md` from Git tags
   and commits.
4. Update every manifest for each affected marketplace plugin with `make update-plugin-versions VERSION=1.3.0 PLUGINS=plugin-name`.
   Omit `PLUGINS=...` only when releasing every plugin at the same version.
5. Run `make check` again. The package validator enforces portable/Claude version parity and exact Claude/Codex manifest parity.
6. Review and commit the changelog and version changes together.
7. Push the commit, then create the tag and GitHub release with `gh skill publish --tag v1.3.0`.

The grouping and filtering rules live in [`cliff.toml`](../cliff.toml). Run `make changelog-check` to validate the
configuration without changing files.
