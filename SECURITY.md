# Security Policy

## Supported versions

Security fixes are applied to the latest released version. Users should upgrade to the newest release before reporting an issue that may already be fixed.

## Reporting a vulnerability

Use GitHub's **Security** tab to submit a private vulnerability report. Do not open a public issue for suspected vulnerabilities or include credentials, Pact contracts, customer data, or exploit details in public discussions.

Useful reports include:

- The affected skill, agent, script, manifest, or workflow
- Reproduction steps and the expected security boundary
- Potential impact, including whether credentials or remote execution are involved
- A minimal proof of concept with secrets and customer data removed

Maintainers aim to acknowledge reports within five business days and will coordinate remediation and disclosure with the reporter. Timing depends on severity and the affected upstream projects.

## Scope

Security-relevant issues include prompt injection or unintended data disclosure in distributed agent instructions, unsafe command execution, credential exposure, dependency or workflow compromise, and bypasses of contract-testing safety checks. General product support and ordinary bugs belong in the public issue tracker.