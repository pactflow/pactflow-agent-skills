# start_mock.ps1 — Start a Prism mock server from an OpenAPI spec (Windows/PowerShell).
#
# Usage:
#   .\start_mock.ps1 --spec openapi.yaml
#   .\start_mock.ps1 --spec openapi.yaml --port 4010
#   .\start_mock.ps1 --spec openapi.yaml --port 4010 --dynamic
#
# Options:
#   --spec      Path to OpenAPI spec (required)
#   --port      Port to listen on (default: 4010)
#   --dynamic   Enable dynamic response generation (Prism generates values from
#               schema rather than using static examples). Useful when the spec
#               has no examples for some responses.
#
# The script installs @stoplight/prism-cli if not already available, then starts
# the server in the foreground. Ctrl-C to stop.

param(
    [string]$spec = "",
    [string]$port = "4010",
    [switch]$dynamic
)

# Support --kebab-case aliases passed as raw args
foreach ($arg in $args) {
    switch -Regex ($arg) {
        "^--spec$"    { $spec    = $args[$args.IndexOf($arg) + 1] }
        "^--port$"    { $port    = $args[$args.IndexOf($arg) + 1] }
        "^--dynamic$" { $dynamic = $true }
    }
}

if (-not $spec) {
    Write-Error "Usage: .\start_mock.ps1 --spec openapi.yaml [--port 4010] [--dynamic]"
    exit 1
}

if (-not (Test-Path $spec)) {
    Write-Error "ERROR: spec file not found: $spec"
    exit 1
}

# Install prism if needed
if (-not (Get-Command prism -ErrorAction SilentlyContinue)) {
    Write-Host "Prism not found -- installing @stoplight/prism-cli globally..."
    npm install -g @stoplight/prism-cli
}

Write-Host "Starting Prism mock server"
Write-Host "  Spec:  $spec"
Write-Host "  Port:  $port"
Write-Host "  URL:   http://localhost:$port"
if ($dynamic) { Write-Host "  Mode:  dynamic (schema-generated responses)" }
Write-Host ""
Write-Host "Use 'Prefer: code=<status>' header to force specific response codes."
Write-Host "Press Ctrl-C to stop."
Write-Host ""

if ($dynamic) {
    prism mock $spec --port $port --dynamic
} else {
    prism mock $spec --port $port
}
