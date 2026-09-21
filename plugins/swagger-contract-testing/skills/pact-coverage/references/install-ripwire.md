# Install ripwire

The pact-coverage skill uses ripwire in two ways:
- **Interactive (Claude Code agent):** via ripwire MCP tools — the `swagger-contract-testing:pact-coverage`
  agent calls ripwire through MCP for adaptive route discovery. Requires MCP setup (see below).
- **CI / headless:** via the ripwire CLI binary — `build_filtered_oas.py` runs `ripwire` as a
  subprocess for Strategy 1 route discovery. Requires only the binary on PATH.

## Check if already installed

```bash
command -v ripwire && ripwire --version
```

## Install prebuilt binary (macOS / Linux, x64 / arm64 — no compiler)

```bash
RIPWIRE_REPO=redhat-et/ripwire \
  bash -c "$(curl -fsSL https://raw.githubusercontent.com/redhat-et/ripwire/main/scripts/install.sh)"
```

The installer detects your platform, downloads the matching binary, and automatically
activates the ripwire skills for every agent it finds on the machine (Claude Code,
Codex, Cursor, Windsurf, Gemini CLI, and others).

Add the binary to `PATH` if the installer says it's needed:

```bash
export PATH="$HOME/.local/bin:$PATH"   # Homebrew machines use brew --prefix/bin instead
```

## Build from source (only if developing ripwire itself)

```bash
git clone https://github.com/redhat-et/ripwire
cd ripwire && ./install.sh
```

Requires cmake and a C++23-capable compiler (clang 17+ or GCC 13+).

---

## Wire ripwire into Claude Code (MCP server — required for the interactive agent)

The release installer already activates the ripwire skills. To expose ripwire's
31 MCP verbs mid-session (warm in-memory graph, no shell round-trip after first parse):

### Via command line (easiest)

```bash
# Register the MCP server
claude mcp add ripwire -- ripwire --mcp

# Install / refresh the skills into ~/.claude/skills/
bash "$(brew --prefix 2>/dev/null || echo "$HOME/.local")/share/ripwire/skills/install.sh"

# Optional: advisory hooks that nudge toward ripwire before Grep/Read
bash "$(brew --prefix 2>/dev/null || echo "$HOME/.local")/share/ripwire/skills/install.sh" --hook
```

### Alternative: add to `mcp.json` (for projects that configure MCP in a file)

```json
{
  "mcpServers": {
    "ripwire": { "command": "ripwire", "args": ["--mcp"] }
  }
}
```

### Verify it's connected

After registering, the `swagger-contract-testing:pact-coverage` agent will check for
`mcp__ripwire__for` availability at startup. If not connected, it will show an error
with the setup link above.

### Quick registration via ripwire's built-in helper

```bash
ripwire wrap claude   # prints: claude mcp add ripwire -- ripwire --mcp
```

### Add ripwire guidance to CLAUDE.md

Then add the following block to your `CLAUDE.md` so every session knows when to reach
for ripwire:

```markdown
## ripwire — deterministic codebase maps (on PATH as `ripwire`)
Reach for it BEFORE blind grep + whole-file reads. First call ~1s cold; after that warm, ~0.1s.
- Orient on a task: `ripwire <dir> --for="<task in words>"` — ranked, quality-annotated signatures.
- One task: `--pack-task="<task>"`.
- Have a stack trace / build error: `ripwire <dir> --from-trace=FILE` (`-` = stdin).
- Who calls X: `--callers=SYM`. Full blast radius: `--impact=SYM` (transitive) + `--uses=SYM`.
- Edit without a whole-file Read: `--replace-symbol-body=SYM --edit-payload=FILE|-`.
- Before writing a new fn/class/helper: `--exemplar="<what you're writing>"`.
- Before calling work done: `--quality-delta`, then `--test-gate`.
Do NOT open a file you have not located first. Do NOT read a whole file to understand one symbol.
```
