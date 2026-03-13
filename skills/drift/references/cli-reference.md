# Drift CLI Reference

## `drift verify`

The primary command. Runs test cases against a live API.

```bash
drift verify --server-url <URL> --test-files <FILE> [OPTIONS]
```

### Required flags

| Flag           | Short | Description                                 |
| -------------- | ----- | ------------------------------------------- |
| `--server-url` | `-u`  | Base URL of the API under test              |
| `--test-files` | `-f`  | Path(s) to test YAML files. Supports globs. |

### Optional flags

| Flag                | Short | Description                                                                |
| ------------------- | ----- | -------------------------------------------------------------------------- |
| `--operation`       |       | Run a single operation by name                                             |
| `--failed`          |       | Re-run only previously failed operations                                   |
| `--tags`            | `-t`  | Filter by tags. Use `!` prefix to exclude. OR logic between multiple tags. |
| `--output-dir`      | `-o`  | Directory for results (default: test file directory)                       |
| `--generate-result` |       | Produce a PactFlow verification bundle for BDCT publishing                 |
| `--log-level`       |       | Verbosity: `TRACE`, `DEBUG`, `INFO` (default), `WARN`, `ERROR`             |

### Examples

```bash
# Basic run
drift verify -u https://api.example.com/v1 -f drift.yaml

# Run against local dev server
drift verify -u http://localhost:8080 -f drift.yaml

# Single operation
drift verify -u http://localhost:8080 -f drift.yaml --operation getProductByID_Success

# Only re-run failed
drift verify -u http://localhost:8080 -f drift.yaml --failed

# Filter by tags (OR logic)
drift verify -u http://localhost:8080 -f drift.yaml --tags smoke
drift verify -u http://localhost:8080 -f drift.yaml --tags products,users
drift verify -u http://localhost:8080 -f drift.yaml --tags '!destructive'

# Multiple test files
drift verify -u http://localhost:8080 -f products.yaml -f users.yaml -f orders.yaml

# Glob pattern
drift verify -u http://localhost:8080 -f "tests/*.yaml"

# Save results
drift verify -u http://localhost:8080 -f drift.yaml --output-dir ./drift-results

# PactFlow BDCT — generate verification bundle
drift verify -u https://api.example.com -f drift.yaml --generate-result

# Debug mode
drift verify -u http://localhost:8080 -f drift.yaml --log-level debug

# Via env var
LOG_LEVEL=DEBUG drift verify -u http://localhost:8080 -f drift.yaml
```

---

## `drift plugins`

Manage Drift plugins.

### `drift plugins installed-plugins`

List all plugins available in your environment.

### `drift plugins default-plugins`

List the built-in bundled plugins.

### `drift plugins info <plugin-file>`

Show metadata for a specific plugin file.

---

## `drift bundle`

Merge multiple verification result directories (used with parallel execution + PactFlow BDCT).

```bash
drift bundle --results dir1 dir2 dir3 --output ./bundled-results
```

---

## `drift check-version`

Check whether a newer version of the Drift binary is available.

---

## `drift init`

Interactive project setup wizard. Scaffolds `drift.yaml`, a Lua file, dataset file, and test file.

```bash
drift init
```

---

## `drift auth logout`

Clear cached PactFlow authentication sessions.

---

## Configuration via environment variables

All non-collection settings accept a `DRIFT_` prefixed uppercase env var:

```bash
DRIFT_HOME_DIR=/path/to/drift/home
LOG_LEVEL=DEBUG
```

PactFlow credentials:

```bash
PACTFLOW_BASE_URL="https://your-workspace.pactflow.io"
PACTFLOW_TOKEN="your-api-token"
```

---

## Configuration file

Create `drift.config.yaml` (or `.toml`, `.json`, `.ini`, `.json5`, `.ron`) in:

- `~/.config/drift/` (Linux)
- `~/Library/Application Support/drift/` (macOS)
- `%APPDATA%\drift\` (Windows)
- `$HOME/.drift/`

```yaml
# drift.config.yaml
log_level: DEBUG
output_dir: ./drift-results
plugin_dir: ./plugins
```

Priority order (highest to lowest): CLI args → env vars → config file

---

## Parallel Execution

Drift doesn't have native parallelism — run multiple files independently and coordinate via CI:

### Shell (local)

```bash
drift verify -u http://localhost:8080 -f pets.yaml --output-dir ./results/pets &
drift verify -u http://localhost:8080 -f store.yaml --output-dir ./results/store &
drift verify -u http://localhost:8080 -f users.yaml --output-dir ./results/users &
wait
```

### GitHub Actions matrix

```yaml
strategy:
  matrix:
    suite: [pets, store, users]
  fail-fast: false

steps:
  - name: Run Drift
    run: drift verify -u http://localhost:8080 -f drift/${{ matrix.suite }}.yaml
```

⚠️ Be careful with stateful tests in parallel — use unique ID ranges or isolated API instances per suite.

---

## JUnit Reports (CI)

Add the `junit-output` plugin to generate XML reports compatible with GitHub Actions, Jenkins, GitLab:

```yaml
plugins:
  - name: oas
  - name: junit-output
```

Then upload artifacts in CI:

```yaml
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: drift-junit-report
    path: ./drift-results
```

---

## Exit Codes

| Code     | Meaning                  |
| -------- | ------------------------ |
| `0`      | All tests passed         |
| non-zero | One or more tests failed |

The exit code is used by CI to fail a build and by `pactflow publish-provider-contract`'s `--verification-exit-code` flag.
