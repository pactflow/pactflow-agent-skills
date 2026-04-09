While you already know this, here is a reminder of the Pact-PHP classes and methods you will need to use to create a Pact test in PHP (having omitted deprecated, unadvised and less important methods):

File: /src/PhpPact/Standalone/MockService/MockServerConfig.php
```
namespace PhpPact\Standalone\MockService;

class MockServerConfig
  public function __construct()
  public function getConsumer(): string
  public function setConsumer(string $consumer): self
  public function getProvider(): string
  public function setProvider(string $provider): self
  public function getHost(): string
  public function setHost(string $host): self
  public function getPort(): int
  public function setPort(int $port): self
  public function getPactDir(): string
  public function setPactDir(string $pactDir): self
  public function getLogDir(): string
  public function setLogDir(string $logDir): self
  public function getLogLevel(): string
  public function setLogLevel(string $logLevel): self
  public function getCors(): bool
  public function setCors(bool $cors): self
  public function getSpec(): int
  public function setSpec(int $spec): self
  public function getConsumerVersion(): string
  public function setConsumerVersion(string $consumerVersion): self
```

File: /src/PhpPact/Consumer/InteractionBuilder.php
```
namespace PhpPact\Consumer;

class InteractionBuilder implements BuilderInterface
  public function __construct(MockServerEnvConfig $config);
  public function given(string $state, array $params = [], bool $overwrite = false): BuilderInterface;
  public function uponReceiving(string $description): BuilderInterface;
  public function with(array $request): BuilderInterface;
  public function willRespondWith(array $response): BuilderInterface;
  public function build(): bool;
  public function getInteraction(): Interaction;
```

File: /src/PhpPact/Config/Config.php
```
namespace PhpPact\Config;

class Config implements ConfigInterface
    public function __construct(string $consumer, string $provider);
    public function getPactDir(): string;
    public function setPactDir(string $pactDir): self;
    public function getLogDir(): string;
    public function setLogDir(string $logDir): self;
    public function getLogLevel(): string;
    public function setLogLevel(string $logLevel): self;
    public function getSpecificationVersion(): string;
    public function setSpecificationVersion(string $specificationVersion): self;
    public function getConsumer(): string;
    public function getProvider(): string;
```

File: /src/PhpPact/Consumer/Matcher/Matcher.php
```
namespace PhpPact\Consumer\Matcher;

class Matcher
  public static function regex(string $value, string $regex): array;
  public static function like($value): array;
  public static function eachLike($value, int $min = 1): array;
  public static function integer(int $value): array;
  public static function decimal(float $value): array;
  public static function boolean(bool $value): array;
  public static function timestamp(string $format = null, string $timestamp = null): array;
  public static function date(string $format = null, string $date = null): array;
  public static function time(string $format = null, string $time = null): array;
```

File: /src/PhpPact/Consumer/Model/ConsumerRequest.php
```
namespace PhpPact\Consumer\Model;

class ConsumerRequest
  public function setMethod(string $method): self;
  public function getMethod(): string;
  public function setPath(string $path): self;
  public function getPath(): string;
  public function setQuery(string $query): self;
  public function getQuery(): string;
  public function setHeaders(array $headers): self;
  public function getHeaders(): array;
  public function setBody($body): self;
  public function getBody();
```

File: /src/PhpPact/Consumer/Model/ProviderResponse.php
```
namespace PhpPact\Consumer\Model;

class ProviderResponse
  public function setStatus(int $status): self;
  public function getStatus(): int;
  public function setHeaders(array $headers): self;
  public function getHeaders(): array;
  public function setBody($body): self;
  public function getBody();
```

File: /src/PhpPact/Consumer/Model/Interaction.php
```
namespace PhpPact\Consumer\Model;

class Interaction
  public function setDescription(string $description): self;
  public function getDescription(): string;
  public function setProviderState(string $providerState): self;
  public function getProviderState(): string;
  public function setRequest(ConsumerRequest $request): self;
  public function getRequest(): ConsumerRequest;
  public function setResponse(ProviderResponse $response): self;
  public function getResponse(): ProviderResponse;
```

File: /src/PhpPact/Consumer/Matcher/Enum/HttpStatus.php
```
namespace PhpPact\Consumer\Matcher\Enum;

enum HttpStatus: int
    case INFORMATION = 'info';
    case SUCCESS = 'success';
    case REDIRECT = 'redirect';
    case CLIENT_ERROR = 'clientError';
    case SERVER_ERROR = 'serverError';
    case NON_ERROR = 'nonError';
    case ERROR = 'error';

    public function range(): Range
```

I'll also include a summary of the generator and matcher classes (omitting the file location and namespace for brevity):

```
class ExpressionFormatter
  public function format(string $expression): string;
class JsonFormatter
	public function format(array $data): string;
class Date
  public function generate(string $format = 'Y-m-d'): string;
class DateTime
	public function generate(string $format = ‘Y-m-d\TH:i:sP’): string;
class MockServerURL
  public function generate(): string;
class ProviderState
	public function generate(string $state): string;
class RandomBoolean
  public function generate(): bool;
class RandomDecimal
	public function generate(): float;
class RandomHexadecimal
  public function generate(int $length = 8): string;
class RandomInt
	public function generate(int $min = 0, int $max = PHP_INT_MAX): int;
class RandomString
  public function generate(int $length = 8): string;
class Regex
	public function generate(string $pattern): string;
class Time
  public function generate(string $format = 'H:i:s'): string;
class Uuid
  public function generate(): string;
class ArrayContains
  public function match(array $expected, array $actual): bool;
class Boolean
  public function match(bool $expected, $actual): bool;
class ContentType
  public function match(string $expected, string $actual): bool;
class Date
  public function match(string $expected, string $actual): bool;
class DateTime
  public function match(string $expected, string $actual): bool;
class Decimal
  public function match(float $expected, $actual): bool;
class EachKey
  public function match(array $expected, array $actual): bool;
class EachValue
  public function match(array $expected, array $actual): bool;
class Equality
  public function match($expected, $actual): bool;
class Includes
  public function match(string $expected, string $actual): bool;
class Integer
  public function match(int $expected, $actual): bool;
class MatchAll
  public function match(array $matchers, $actual): bool;
class MatchingField
  public function match($expected, $actual): bool;
class Max
  public function match($expected, $actual): bool;
class MaxType
  public function match($expected, $actual): bool;
class Min
  public function match($expected, $actual): bool;
class MinMaxType
  public function match($expected, $actual): bool;
class MinType
  public function match($expected, $actual): bool;
class NotEmpty
  public function match($actual): bool;
class NullValue
  public function match($actual): bool;
class Number
  public function match($expected, $actual): bool;
class Regex
  public function match(string $pattern, string $actual): bool;
class Semver
  public function match(string $expected, string $actual): bool;
class StatusCode
  public function match(int $expected, int $actual): bool;
```
