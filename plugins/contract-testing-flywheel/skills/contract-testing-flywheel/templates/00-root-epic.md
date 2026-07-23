# {{title: Contract Testing Onboarding: {{team}} ({{consumer}} ↔ {{provider}})}}

## Why this {{root_term}} exists

This {{root_term}} tracks {{team}}'s end-to-end onboarding to contract testing — from the first planning conversation through to a published consumer contract, a verified provider contract, and a `can-i-deploy` gate wired into CI. It exists so the team has a single place to triage and sequence the work, not a checklist of disconnected tasks.

The structure follows the Contract Testing Flywheel: Planning → Requirements → Design → Implementation → Testing → Deployment → Lessons-Learned (with an optional Management Dashboard). Every child {{delivery_term}} / Task has its own AC, link bundle, and tooling suggestions.

## Scope of this onboarding

- **Consumer:** {{consumer}}
- **Provider:** {{provider}}
- **Stack:** {{stack}}
- **CT mode:** {{ct_mode}}
- **Broker:** {{broker_url_or_phrase}}
- **CI tool:** {{ci_tool}}

Rerun `/contract-testing-flywheel` for additional consumer/provider pairs; one {{root_term}} per pair keeps each backlog cleanly scoped.

## Definition of done for the {{root_term}}

- Phases 1–7 complete; their acceptance criteria are all met.
- {{consumer}}'s contract is published to the broker and visible in the matrix.
- {{provider}}'s verification passes against {{consumer}}'s latest published contract.
- `can-i-deploy` runs in both deploy pipelines and gates merges to release branches.
- The team has captured lessons-learned and best practices in their internal wiki (Phase 7).
- (If opted-in) Phase 8's management dashboard is live and shared with engineering management.

## References

- [Pact docs](https://docs.pact.io)
- [PactFlow docs](https://docs.pactflow.io)
- [Pact Nirvana ladder](https://docs.pact.io/pact_nirvana)
- [{{pact_library}}]({{pact_library_url}})

---
*If you're using Claude Code: `/swagger-contract-testing` provides end-to-end help authoring + running contract tests. `smartbear-mcp` offers AI-assisted test generation + PactFlow operations.*
