While you already know this, here is a reminder of the Pact-JS classes and methods you will need to use to create a Pact test in TypeScript (having omitted deprecated and unadvised methods):

File: /v3/pact.ts
```
// import { PactV3 } from "@pact-foundation/pact";
class PactV3 {
    constructor(opts: PactV3Options);
    addInteraction(interaction: V3Interaction): PactV3;
    given(providerState: string, parameters?: JsonMap): PactV3;
    uponReceiving(description: string): PactV3;
    withRequest(req: V3Request): PactV3;
    withRequestBinaryFile(req: V3Request, contentType: string, file: string): PactV3;
    withRequestMultipartFileUpload(req: V3Request, contentType: string, file: string, mimePartName: string): PactV3;
    willRespondWith(res: V3Response): PactV3;
    withResponseBinaryFile(res: V3Response, contentType: string, file: string): PactV3;
    withResponseMultipartFileUpload(res: V3Response, contentType: string, file: string, mimePartName: string): PactV3;
    executeTest<T>(testFn: (mockServer: V3MockServer) => Promise<T>): Promise<T | undefined>;
}
```

File: /v3/matchers.ts
```
// import { MatchersV3 } from "@pact-foundation/pact";
module MatchersV3 {
    function isMatcher(x: unknown): x is Matcher<unknown>;
    const like: <T>(template: T) => Matcher<T>;
    const eachKeyLike: <T>(keyTemplate: string, template: T) => Matcher<T>;
    const eachKeyMatches: (example: Record<string, unknown>, matchers?: Matcher<string> | Matcher<string>[]) => RulesMatcher<unknown>;
    const eachValueMatches: <T>(example: Record<string, T>, matchers: Matcher<T> | Matcher<T>[]) => RulesMatcher<T>;
    const eachLike: <T>(template: T, min?: number) => MinLikeMatcher<T[]>;
    const atLeastOneLike: <T>(template: T, count?: number) => MinLikeMatcher<T[]>;
    const atLeastLike: <T>(template: T, min: number, count?: number) => MinLikeMatcher<T[]>;
    const atMostLike: <T>(template: T, max: number, count?: number) => MaxLikeMatcher<T[]>;
    const constrainedArrayLike: <T>(template: T, min: number, max: number, count?: number) => MinLikeMatcher<T[]> & MaxLikeMatcher<T[]>;
    const boolean: (b?: boolean) => Matcher<boolean>;
    const integer: (int?: number) => Matcher<number>;
    function number(num?: number): Matcher<number>;
    function string(str?: string): Matcher<string>;
    function regex(pattern: RegExp | string, str: string): V3RegexMatcher;
    const equal: <T>(value: T) => Matcher<T>;
    function datetime(format: string, example: string): DateTimeMatcher;
    function timestamp(format: string, example: string): DateTimeMatcher;
    function time(format: string, example: string): DateTimeMatcher;
    function date(format: string, example: string): DateTimeMatcher;
    function includes(value: string): Matcher<string>;
    function nullValue(): Matcher<null>;
    function url2(basePath: string | null, pathFragments: Array<string | V3RegexMatcher | RegExp>): V3RegexMatcher;
    function url(pathFragments: Array<string | V3RegexMatcher | RegExp>): V3RegexMatcher;
    function arrayContaining(...variants: unknown[]): ArrayContainsMatcher;
    function fromProviderState<V>(expression: string, exampleValue: V): ProviderStateInjectedValue<V>;
    function uuid(example?: string): V3RegexMatcher;
    const matcherValueOrString: (obj: unknown) => string;
    function reify(input: unknown): AnyJson;
    const extractPayload: typeof reify;
}
```

File: /v3/xml/xmlBuilder.ts
```
class XmlBuilder {
    build(callback: (doc: XmlElement) => void): string;
}
```

File: /v3/xml/xmlElement.ts
```
type XmlAttributes = Map<string, string>;
type XmlCallback = (n: XmlElement) => void;

class XmlElement {
    setName(name: string): XmlElement;
    setAttributes(attributes: XmlAttributes): XmlElement;
    appendElement(name: string, attributes: XmlAttributes, arg?: string | XmlCallback | Matcher<string>): XmlElement;
    appendText(content: string | Matcher<string>): XmlElement;
    eachLike(name: string, attributes: XmlAttributes, cb?: XmlCallback, options: EachLikeOptions = { examples: 1 }): XmlElement;
}

interface EachLikeOptions {
    min?: number;
    max?: number;
    examples?: number;
}
```

File: /v3/xml/xmlNode.ts
```
class XmlNode {}
```

File: /v3/xml/xmlText.ts
```
class XmlText {
    constructor(content: string, matcher?: Matcher<string>);
}
```

File: /dsl/interaction.ts
```
interface QueryObject {
  [name: string]: string | Matcher<string> | string[];
}
type Query = string | QueryObject;
type Headers = {
  [header: string]: string | Matcher<string> | (Matcher<string> | string)[];
};
interface RequestOptions {
  method: HTTPMethods | HTTPMethod;
  path: string | Matcher<string>;
  query?: Query;
  headers?: Headers;
  body?: AnyTemplate;
}
interface ResponseOptions {
  status: number;
  headers?: Headers;
  body?: AnyTemplate;
}
interface InteractionObject {
  state: string | undefined;
  uponReceiving: string;
  withRequest: RequestOptions;
  willRespondWith: ResponseOptions;
}
interface InteractionState {
  providerState?: string;
  description?: string;
  request?: RequestOptions;
  response?: ResponseOptions;
}
interface InteractionStateComplete {
  providerState?: string;
  description: string;
  request: RequestOptions;
  response: ResponseOptions;
}
class Interaction {
  given(providerState: string): this;
  uponReceiving(description: string): this;
  withRequest(requestOpts: RequestOptions): this;
  willRespondWith(responseOpts: ResponseOptions): this;
  json(): InteractionStateComplete;
}
const interactionToInteractionObject(interaction: InteractionStateComplete): InteractionObject;
```

File: /dsl/options.ts
```
type LogLevel: 'trace' | 'debug' | 'info' | 'warn' | 'error';
interface PactOptions {
    consumer: string;
    provider: string;
    port?: number;
    host?: string;
    ssl?: boolean;
    sslcert?: string;
    sslkey?: string;
    dir?: string;
    log?: string;
    logLevel?: LogLevel;
    spec?: number;
    cors?: boolean;
    timeout?: number;
    pactfileWriteMode?: PactfileWriteMode;
}
interface MandatoryPactOptions {
    port: number;
    host: string;
    ssl: boolean;
}
type PactOptionsComplete = PactOptions & MandatoryPactOptions;
interface MessageProviderOptions {
    logLevel?: LogLevel;
    messageProviders: MessageProviders;
    stateHandlers?: MessageStateHandlers;
}
type ExcludedPactNodeVerifierKeys = Exclude<keyof PactCoreVerifierOptions, 'providerBaseUrl'>;
type PactNodeVerificationExcludedOptions = Pick<PactCoreVerifierOptions, ExcludedPactNodeVerifierKeys>;
type PactMessageProviderOptions = PactNodeVerificationExcludedOptions & MessageProviderOptions;
interface MessageConsumerOptions {
    consumer: string;
    dir?: string;
    provider: string;
    log?: string;
    logLevel?: LogLevel;
    spec?: number;
    pactfileWriteMode?: PactfileWriteMode;
}
```

File: /dsl/verifier/verifier.ts
```
class Verifier {
    constructor(config: VerifierOptions);
    verifyProvider(): Promise<string>;
}
```

File: /dsl/verifier/proxy/messages.ts
```
export const providerWithMetadata(provider: MessageProvider, metadata: Record<string, string>): MessageProvider;
```

File: /dsl/verifier/proxy/types.ts
```
type Hook: () => Promise<unknown>;
interface StateHandlers {
  [name: string]: StateHandler;
}
interface ProviderState {
  action: StateAction;
  params: JsonMap;
  state: string;
}
type StateAction: 'setup' | 'teardown';
type StateFunc: (parameters?: AnyJson) => Promise<JsonMap | void>;
type StateFuncWithSetup: {
  setup?: StateFunc;
  teardown?: StateFunc;
};
type StateHandler: StateFuncWithSetup | StateFunc;
```
