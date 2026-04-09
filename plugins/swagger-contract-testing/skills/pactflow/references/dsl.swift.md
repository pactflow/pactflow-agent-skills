While you already know this, here is a reminder of the key PactSwift classes, types, structs and methods you will need to use to create a Pact test in Swift (having omitted deprecated and unadvised methods):

File: MockService.swift
```
open class MockService
	public convenience init(
		consumer: String,
		provider: String,
		scheme: TransferProtocol = .standard,
		writePactTo directory: URL? = nil,
		merge: Bool = true
	)
	public func uponReceiving(_ description: String) -> Interaction
	public func run(
		_ file: FileString? = #file,
		line: UInt? = #line,
		verify interactions: [Interaction]? = nil,
		timeout: TimeInterval? = nil,
		testFunction: @escaping (_ baseURL: String, _ done: (@escaping @Sendable () -> Void)) throws -> Void
	)
```

File: MockService+Concurrency.swift
```
extension MockService {
	public func run(
		verify interactions: [Interaction]? = nil,
		timeout: TimeInterval? = nil,
		testFunction: @escaping (_ baseURL: String) async throws -> Void
	)
}
```

File: MockService+Extension.swift
```
extension MockService
	public func given(_ providerState: String) -> Interaction
```

File: Model/Interaction.swift
```
public class Interaction
	public init(description: String, providerStates: [ProviderState], request: Request, response: Response)
```

File: Model/PactHTTPMethod.swift
```
public enum PactHTTPMethod: String {
	case GET
	case POST
	case PUT
	case DELETE
	case PATCH
	case HEAD
	case OPTIONS
}
```

File: Model/ProviderState.swift
```
public struct ProviderState
	public init(description: String, parameters: [String: Any]? = nil)
```

File: Model/Request.swift
```
public struct Request
	public init(method: PactHTTPMethod, path: String, query: [String: String]? = nil, headers: [String: String]? = nil, body: Any? = nil)
```

File: Model/Response.swift
```
public struct Response
	public init(status: Int, headers: [String: String]? = nil, body: Any? = nil)
```

I'll also include a summary of the generator and matcher classes (omitting the file location and namespace for brevity):

```
public struct FromProviderState: Matcher
	public init(_ expression: String, example: Any)
public struct OneOf: Matcher
	public init(_ variants: [Any])
public struct SomethingLike: Matcher
	public init(_ value: Any)
public struct EqualTo: Matcher
	public init(_ value: Any)
public struct EachLike: Matcher
	public init(_ value: Any, min: Int = 1, max: Int? = nil)
public struct EachKeyLike: Matcher
	public init(_ key: String, value: Any)
public struct IntegerLike: Matcher
	public init(_ value: Int)
public struct RegexLike: Matcher
	public init(_ pattern: String, example: String)
public struct IncludesLike: Matcher
	public init(_ value: String)
public struct DecimalLike: Matcher
	public init(_ value: Decimal)
public struct MatchNull: Matcher
	public init()
public struct RandomBool: ExampleGenerator
	public init()
public struct RandomString: ExampleGenerator
	public init(size: Int)
public struct RandomDateTime: ExampleGenerator
	public init()
public struct RandomDecimal: ExampleGenerator
	public init()
public struct RandomHexadecimal: ExampleGenerator
	public init(size: Int)
public struct RandomInt: ExampleGenerator
	public init(min: Int, max: Int)
public struct DateTimeExpression: ExampleGenerator
	public init(_ expression: String)
public struct RandomTime: ExampleGenerator
	public init()
public struct RandomUUID: ExampleGenerator
	public init()
public struct RandomDate: ExampleGenerator
	public init()
public struct ProviderStateGenerator: ExampleGenerator
	public init(_ expression: String)
public struct DateTime: ExampleGenerator
	public init(format: String)
```
