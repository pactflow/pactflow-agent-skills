# Working with Real-World Spec Collections

Commands for navigating and querying large OpenAPI spec repositories.

---

## konfig-sdks/openapi-examples

Specs live at `<repo-root>/<provider>/openapi.yaml` (sometimes nested, e.g.
`atlassian/jira/openapi.yaml`). The most complex specs — all five patterns simultaneously
— are: `snyk`, `digitalocean`, `posthog`, `front/core`.

```bash
# List all endpoints in a spec (macOS/Linux/Git Bash/WSL)
grep "^  /" spec.yaml

# Find endpoints with polymorphic schemas
grep -n "oneOf\|anyOf\|discriminator" spec.yaml

# Find specs using all five complexity patterns
for f in $(find . -name "openapi.yaml"); do
  score=0
  grep -q "anyOf" "$f" && score=$((score+1))
  grep -q "oneOf" "$f" && score=$((score+1))
  grep -q "allOf" "$f" && score=$((score+1))
  grep -q "discriminator" "$f" && score=$((score+1))
  grep -q "pattern:" "$f" && score=$((score+1))
  [ $score -ge 4 ] && echo "$score $f"
done | sort -rn
```

```powershell
# PowerShell equivalents (Windows)

# List all endpoints in a spec
Select-String -Path spec.yaml -Pattern "^  /" | Select-Object -ExpandProperty Line

# Find endpoints with polymorphic schemas
Select-String -Path spec.yaml -Pattern "oneOf|anyOf|discriminator" | Select-Object LineNumber, Line

# Find specs using all five complexity patterns
Get-ChildItem -Recurse -Filter "openapi.yaml" | ForEach-Object {
  $f = $_.FullName
  $score = 0
  if (Select-String -Path $f -Pattern "anyOf"        -Quiet) { $score++ }
  if (Select-String -Path $f -Pattern "oneOf"        -Quiet) { $score++ }
  if (Select-String -Path $f -Pattern "allOf"        -Quiet) { $score++ }
  if (Select-String -Path $f -Pattern "discriminator" -Quiet) { $score++ }
  if (Select-String -Path $f -Pattern "pattern:"     -Quiet) { $score++ }
  if ($score -ge 4) { "$score $f" }
} | Sort-Object -Descending
```
