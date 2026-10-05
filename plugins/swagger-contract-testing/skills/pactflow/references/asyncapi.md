# AsyncAPI Provider Contracts

PactFlow Bi-Directional Contract Testing can compare consumer Pact message interactions with a provider's AsyncAPI definition. Use this flow for event-driven APIs; use `pact-messages.md` for standard message Pact tests where the provider verifies generated messages directly.

Sources:

- [AsyncAPI support](https://support.smartbear.com/swagger/contract-testing/docs/en/user-guide/contract-testing/bi-directional-contract-testing/supported-contracts/asyncapi.html)
- [AsyncAPI contracts overview](https://support.smartbear.com/swagger/contract-testing/docs/en/user-guide/contract-testing/bi-directional-contract-testing/supported-contracts/asyncapi/asyncapi-contracts---overview.html)
- [Testing AsyncAPI](https://support.smartbear.com/swagger/contract-testing/docs/en/user-guide/contract-testing/bi-directional-contract-testing/supported-contracts/asyncapi/features-testing-asyncapi.html)

## Support Matrix

| Capability | Support |
| --- | --- |
| AsyncAPI 3.0 and 3.1 | Supported, including any patch version |
| AsyncAPI 2.x | Not supported |
| Message payload | JSON only |
| Avro and Protobuf payloads | Not currently compared |
| Internal `$ref` | Supported |
| External `$ref` | Not supported; the definition must be self-contained |
| Channel/topic names | Exact name matching |
| Binding-specific behavior | Not validated, including partitions, security policies, and schema registry integration |
| Pact matching rules | Ignored during AsyncAPI verification |

The root `asyncapi` value must be a full `major.minor.patch` version such as `3.0.0`. Upload validates the declared version and document structure. Unsupported payload formats may produce a notice rather than rejecting the whole definition, but those messages are not covered by cross-contract verification.

AsyncAPI provider contracts are available in PactFlow Cloud and PactFlow On-Premises 2.6.0 and later.

## Contract Mapping

The provider publishes one AsyncAPI definition. The consumer publishes a Pact V3 or V4 contract containing message interactions.

| Messaging pattern | Provider-perspective AsyncAPI operation | Pact interaction |
| --- | --- | --- |
| Fire-and-forget | `receive` | V3 asynchronous message or V4 `Asynchronous/Messages` |
| Request/reply | `send` with a `reply` block | V4 `Synchronous/Messages` |

Do not infer the direction from the operation name. Follow the provider-perspective action shown in the table.

Each Pact interaction must identify the AsyncAPI operation:

```json
{
  "comments": {
    "references": {
      "AsyncAPI": {
        "operationId": "receiveUserEvents"
      }
    }
  }
}
```

In Pact JS V4, add the reference with:

```javascript
.reference('AsyncAPI', 'operationId', 'receiveUserEvents')
```

A provider can publish either an OpenAPI definition or an AsyncAPI definition, not both at the same time. A consumer Pact may contain both HTTP and message interactions; cross-contract verification compares only interactions matching the provider contract type.

## Verification Semantics

For each interaction, PactFlow:

1. Reads the AsyncAPI `operationId` reference from the Pact interaction comments.
2. Finds that operation in the AsyncAPI definition.
3. Compares the message payload with each candidate message on the operation.
4. Compares metadata, such as headers, with the message headers schema.
5. For request/reply interactions, compares the response with the reply channel messages.

The interaction passes when its payload and metadata match at least one candidate message.

Validation is asymmetric:

- **Sender:** payload must match the schema exactly; all required fields must be present and no extra fields are allowed.
- **Receiver:** payload may be a valid subset; required schema fields must be present and the receiver may ignore extra fields.
- **Channel/topic and content type:** channel names match exactly and content type must be JSON.

Pact matching rules do not affect this comparison. Ensure the concrete payload and metadata values in the Pact are valid against the AsyncAPI schemas.

## Publication Workflow

1. Validate and self-test the provider implementation against its AsyncAPI definition.
2. Publish the AsyncAPI provider contract and successful self-verification result for the provider version.
3. Publish consumer Pact V3/V4 message contracts containing AsyncAPI operation references.
4. Inspect the BDCT cross-contract verification result.
5. Run `can-i-deploy`, then record the deployment.

Use `contract-testing_publish_provider_contract` when its `contract.specification` input accepts AsyncAPI. If the connected MCP server exposes only `oas`, use the PactFlow CLI `pactflow publish-provider-contract` instead of labelling an AsyncAPI document as OpenAPI. Never publish an AsyncAPI definition with `specification: "oas"`.

## Troubleshooting

| Result | Meaning | Check |
| --- | --- | --- |
| `message.matched` | Interaction matched | No action required |
| `message.no.match` | No candidate message matched | Operation ID, payload, metadata, and content type |
| `message.reply.missing` | Pact expects a response but the operation has no `reply` | Add `reply` or remove the expected response |
| `message.response.missing` | Operation has `reply` but Pact has no response | Add the Pact response or remove `reply` |
| `(unknown operation)` | Referenced operation ID does not exist | Correct the interaction reference |
| `(spec missing)` | Provider has no published AsyncAPI definition | Publish the provider contract |
| `(references missing)` | A `$ref` cannot be resolved | Make all references internal and resolvable |

Use the BDCT retrieval tools in `bdct.md` to inspect provider contracts, consumer contracts, self-verification results, and cross-contract verification results for a specific version pair.
