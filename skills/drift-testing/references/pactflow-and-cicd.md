# PactFlow Integration & CI/CD

## Contents

- [Bi-Directional Contract Testing (BDCT) with PactFlow](#bi-directional-contract-testing-bdct-with-pactflow)
- [GitHub Actions — Full Workflow](#github-actions--full-workflow)
- [GitHub Actions — Parallel Suites](#github-actions--parallel-suites)
- [GitLab CI](#gitlab-ci)
- [Embedding in Test Frameworks](#embedding-in-test-frameworks)

---

## Bi-Directional Contract Testing (BDCT) with PactFlow

Drift generates provider-side verification results that PactFlow uses for BDCT. Set credentials as described in `auth.md#pactflow-auth`.

### Full publish workflow

```bash
# Step 1: Run tests and generate verification bundle
drift verify \
  --test-files drift.yaml \
  --server-url https://api.example.com/v1 \
  --generate-result \
  --output-dir ./drift-results

EXIT_CODE=$?

# Step 2: Publish to PactFlow
pactflow publish-provider-contract \
  --provider my-api \
  --provider-app-version $(git rev-parse --short HEAD) \
  --branch $(git branch --show-current) \
  --verification-exit-code $EXIT_CODE \
  --verification-results ./drift-results/verification-bundle.json \
  --verification-results-content-type application/vnd.smartbear.drift.result \
  --spec openapi.yaml \
  --spec-content-type application/yaml
```

`--verification-exit-code` must match the actual Drift exit code, even if tests fail.

### Bundling parallel suite results

Merge parallel suite results before publishing:

```bash
drift bundle \
  --results ./results/pets ./results/store ./results/users \
  --output ./bundled-results

pactflow publish-provider-contract \
  --verification-results ./bundled-results/verification-bundle.json \
  # ... other flags
```

---

## GitHub Actions — Full Workflow

```yaml
name: API Contract Tests

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  drift-test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install Drift
        run: |
          wget -O - https://download.pactflow.io/drift/latest/linux-x86_64.tgz | tar xz -C /usr/local/bin
          drift --version

      - name: Install dependencies & start API
        run: |
          npm install
          npm start &
          sleep 5   # wait for server to be ready

      - name: Run Drift Tests
        run: |
          drift verify \
            --test-files drift.yaml \
            --server-url http://localhost:8080 \
            --output-dir ./drift-results \
            --generate-result
          echo "DRIFT_EXIT_CODE=$?" >> $GITHUB_ENV
        env:
          API_TOKEN: ${{ secrets.API_TOKEN }}
        continue-on-error: true   # don't stop — still need to publish

      - name: Publish to PactFlow
        run: |
          pactflow publish-provider-contract \
            --provider payments-api \
            --provider-app-version ${{ github.sha }} \
            --branch ${{ github.head_ref || github.ref_name }} \
            --verification-exit-code ${{ env.DRIFT_EXIT_CODE }} \
            --verification-results ./drift-results/verification-bundle.json \
            --verification-results-content-type application/vnd.smartbear.drift.result \
            --spec openapi.yaml \
            --spec-content-type application/yaml
        env:
          PACTFLOW_BASE_URL: ${{ secrets.PACTFLOW_BASE_URL }}
          PACTFLOW_TOKEN: ${{ secrets.PACTFLOW_TOKEN }}

      - name: Archive Test Results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: drift-results
          path: ./drift-results

      - name: Fail if tests failed
        if: env.DRIFT_EXIT_CODE != '0'
        run: exit 1
```

---

## GitHub Actions — Parallel Suites

```yaml
jobs:
  drift-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        suite: [products, users, orders]
      fail-fast: false

    steps:
      - uses: actions/checkout@v4
      - name: Install Drift
        run: npm install -g @pactflow/drift

      - name: Start API
        run: npm start &

      - name: Run suite
        run: |
          drift verify \
            --test-files tests/${{ matrix.suite }}.yaml \
            --server-url http://localhost:8080 \
            --output-dir ./results/${{ matrix.suite }} \
            --generate-result

      - name: Upload results
        uses: actions/upload-artifact@v4
        with:
          name: drift-results-${{ matrix.suite }}
          path: ./results/${{ matrix.suite }}

  publish:
    needs: drift-test
    runs-on: ubuntu-latest
    steps:
      - name: Download all results
        uses: actions/download-artifact@v4
        with:
          pattern: drift-results-*
          merge-multiple: true
          path: ./all-results

      - name: Bundle results
        run: |
          drift bundle \
            --results ./all-results/products ./all-results/users ./all-results/orders \
            --output ./bundled

      - name: Publish to PactFlow
        run: |
          pactflow publish-provider-contract \
            --provider my-api \
            --provider-app-version ${{ github.sha }} \
            --branch ${{ github.ref_name }} \
            --verification-exit-code 0 \
            --verification-results ./bundled/verification-bundle.json \
            --verification-results-content-type application/vnd.smartbear.drift.result \
            --spec openapi.yaml \
            --spec-content-type application/yaml
        env:
          PACTFLOW_BASE_URL: ${{ secrets.PACTFLOW_BASE_URL }}
          PACTFLOW_TOKEN: ${{ secrets.PACTFLOW_TOKEN }}
```

---

## GitLab CI

```yaml
test:
  image: node:20
  services:
    - postgres:15
  before_script:
    - wget -O - https://download.pactflow.io/drift/latest/linux-x86_64.tgz | tar xz -C /usr/local/bin
    - drift --version
    - npm install
  script:
    - npm start &
    - sleep 5
    - drift verify -f drift.yaml -u http://localhost:8080 --generate-result --output-dir ./drift-results
  artifacts:
    paths:
      - drift-results/
    when: always
  variables:
    POSTGRES_DB: testdb
    POSTGRES_PASSWORD: test
```

---

## Embedding in Test Frameworks

Use Drift as a subprocess within Jest, pytest, or other frameworks so contract tests run
alongside unit/integration tests with shared infrastructure.

### Jest

```javascript
// automation/drift.js
const { spawn } = require('child_process');

const runDrift = (options = {}) => {
  const { testFile = './drift.yaml', serverUrl = 'http://localhost:8080',
          outputDir = './output', logLevel = 'info' } = options;

  return new Promise((resolve, reject) => {
    const child = spawn('drift', [
      'verify', '--test-files', testFile, '--server-url', serverUrl,
      '--log-level', logLevel, '--output-dir', outputDir
    ], { stdio: 'inherit', shell: true });
    child.on('error', reject);
    child.on('close', (code) => resolve(code ?? 1));
  });
};

module.exports = { runDrift };
```

```javascript
// tests/contract.test.js
const { runDrift } = require('../automation/drift');
const express = require('express');

describe('API Contract Tests', () => {
  let server;

  beforeAll(async () => {
    const app = express();
    app.use(require('../src/routes'));
    server = app.listen(8080);
  });

  afterAll(() => new Promise(resolve => server.close(resolve)));

  it('conforms to OpenAPI specification', async () => {
    const exitCode = await runDrift({ serverUrl: 'http://localhost:8080' });
    expect(exitCode).toBe(0);
  });
});
```

### pytest

```python
import subprocess
import pytest

def run_drift(test_file='./drift.yaml', server_url='http://localhost:8080'):
    result = subprocess.run([
        'drift', 'verify', '--test-files', test_file, '--server-url', server_url
    ])
    return result.returncode

def test_api_conforms_to_openapi_spec(api_server):
    assert run_drift() == 0, "Drift contract tests failed — API has drifted from spec"
```
