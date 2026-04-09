While you already know this, here is a reminder of the key Pact Go interfaces, types, structs and methods you will need to use to create a Pact test in Golang (having omitted deprecated and unadvised methods):

File: ./models/pact_file.go
```
package models

type SpecificationVersion string

const (
	V2 SpecificationVersion = "2.0.0"
	V3 = "3.0.0"
	V4 = "4.0.0"
)
```

File: ./models/provider_state.go
```
package models

type ProviderState struct {
	Name string `json:"name"`
	Parameters map[string]interface{} `json:"params,omitempty"`
}

type ProviderStateResponse map[string]interface{}
type StateHandler func(setup bool, state ProviderState) (ProviderStateResponse, error)
type StateHandlers map[string]StateHandler
```

File: ./log/log.go
```
package log

func SetLogLevel(level logutils.LogLevel) error
func LogLevel() logutils.LogLevel
```

File: ./matchers/matcher.go
```
package matchers

func EachLike(content interface{}, minRequired int) Matcher
var ArrayMinLike func(content interface{}, minRequired int) Matcher
func Like(content interface{}) Matcher
func Term(generate string, matcher string) Matcher
func HexValue() Matcher
func Identifier() Matcher
func IPAddress() Matcher
var IPv4Address func() Matcher
func IPv6Address() Matcher
```

File: ./matchers/matcher_v3.go
```
package matchers

func Decimal(example float64) Matcher
func Integer(example int) Matcher
type Null struct{}
func (n Null) GetValue() interface{}
func (n Null) MarshalJSON() ([]byte, error)
func Equality(content interface{}) Matcher
func Includes(content string) Matcher
func FromProviderState(expression, example string) Matcher
func EachKeyLike(key string, template interface{}) Matcher
func ArrayContaining(variants []interface{}) Matcher
func ArrayMinMaxLike(content interface{}, min int, max int) Matcher
func ArrayMaxLike(content interface{}, max int) Matcher
func DateGenerated(example string, format string) Matcher
func TimeGenerated(example string, format string) Matcher
func DateTimeGenerated(example string, format string) Matcher
```

File: ./consumer/interaction.go
```
package consumer

type Interaction struct {
	interaction          interface{}
	specificationVersion models.SpecificationVersion
}

func (i *Interaction) WithCompleteRequest(request Request) *Interaction
func (i *Interaction) WithCompleteResponse(response Response) *Interaction
```

File: ./consumer/http_v3.go
```
package consumer

type V3HTTPMockProvider struct {
	*httpMockProvider
}

func NewV3Pact(config MockHTTPProviderConfig) (*V3HTTPMockProvider, error)
func (p *V3HTTPMockProvider) AddInteraction() *V3UnconfiguredInteraction
type V3UnconfiguredInteraction struct {
	interaction *Interaction
	provider    *V3HTTPMockProvider
}
func (i *V3UnconfiguredInteraction) Given(state string) *V3UnconfiguredInteraction
func (i *V3UnconfiguredInteraction) GivenWithParameter(state models.ProviderState) *V3UnconfiguredInteraction
func (i *V3UnconfiguredInteraction) UponReceiving(description string) *V3UnconfiguredInteraction
func (i *V3UnconfiguredInteraction) WithCompleteRequest(request Request) *V3InteractionWithCompleteRequest
func (i *V3UnconfiguredInteraction) WithRequest(method Method, path string, builders ...V3RequestBuilderFunc) *V3InteractionWithRequest
func (i *V3UnconfiguredInteraction) WithRequestPathMatcher(method Method, path matchers.Matcher, builders ...V3RequestBuilderFunc) *V3InteractionWithRequest
type V3InteractionWithRequest struct {
	interaction *Interaction
	provider    *V3HTTPMockProvider
}
func (i *V3InteractionWithRequest) WillRespondWith(status int, builders ...V3ResponseBuilderFunc) *V3InteractionWithResponse
type V3InteractionWithCompleteRequest struct {}
func (i *V3InteractionWithCompleteRequest) WithCompleteResponse(response Response) *V3InteractionWithResponse
type V3InteractionWithResponse struct {}
type V3RequestBuilderFunc func(*V3RequestBuilder)
type V3RequestBuilder struct {}
func (i *V3RequestBuilder) Query(key string, values ...matchers.Matcher) *V3RequestBuilder
func (i *V3RequestBuilder) Header(key string, values ...matchers.Matcher) *V3RequestBuilder
func (i *V3RequestBuilder) Headers(headers matchers.HeadersMatcher) *V3RequestBuilder
func (i *V3RequestBuilder) JSONBody(body interface{}) *V3RequestBuilder
func (i *V3RequestBuilder) BinaryBody(body []byte) *V3RequestBuilder
func (i *V3RequestBuilder) MultipartBody(contentType string, filename string, mimePartName string) *V3RequestBuilder
func (i *V3RequestBuilder) Body(contentType string, body []byte) *V3RequestBuilder
func (i *V3RequestBuilder) BodyMatch(body interface{}) *V3RequestBuilder
type V3ResponseBuilderFunc func(*V3ResponseBuilder)
type V3ResponseBuilder struct {}
func (i *V3ResponseBuilder) Header(key string, values ...matchers.Matcher) *V3ResponseBuilder
func (i *V3ResponseBuilder) Headers(headers matchers.HeadersMatcher) *V3ResponseBuilder
func (i *V3ResponseBuilder) JSONBody(body interface{}) *V3ResponseBuilder
func (i *V3ResponseBuilder) BinaryBody(body []byte) *V3ResponseBuilder
func (i *V3ResponseBuilder) MultipartBody(contentType string, filename string, mimePartName string) *V3ResponseBuilder
```

File: ./consumer/response.go
```
package consumer

// Response is the default implementation of the Response interface.
type Response struct {
	Status  int
	Headers matchers.MapMatcher
	Body    interface{}
}
```

File: ./consumer/request.go
```
package consumer

type Request struct {
	Method  string
	Path    matchers.Matcher
	Query   matchers.MapMatcher
	Headers matchers.MapMatcher
	Body    interface{}
}
type Method string
```

File: ./consumer/http_v2.go
```
package consumer

type V2HTTPMockProvider struct {}

func NewV2Pact(config MockHTTPProviderConfig) (*V2HTTPMockProvider, error)
func (p *V2HTTPMockProvider) AddInteraction() *V2UnconfiguredInteraction
type V2UnconfiguredInteraction struct {}
func (i *V2UnconfiguredInteraction) Given(state string) *V2UnconfiguredInteraction
func (i *V2UnconfiguredInteraction) UponReceiving(description string) *V2UnconfiguredInteraction
func (i *V2UnconfiguredInteraction) WithCompleteRequest(request Request) *V2InteractionWithCompleteRequest
func (i *V2UnconfiguredInteraction) WithRequest(method Method, path string, builders ...V2RequestBuilderFunc) *V2InteractionWithRequest
func (i *V2UnconfiguredInteraction) WithRequestPathMatcher(method Method, path matchers.Matcher, builders ...V2RequestBuilderFunc) *V2InteractionWithRequest
type V2InteractionWithRequest struct {}
func (i *V2InteractionWithRequest) WillRespondWith(status int, builders ...V2ResponseBuilderFunc) *V2InteractionWithResponse
type V2InteractionWithCompleteRequest struct {}
func (i *V2InteractionWithCompleteRequest) WithCompleteResponse(response Response) *V2InteractionWithResponse
type V2InteractionWithResponse struct {}
type V2RequestBuilderFunc func(*V2RequestBuilder)
type V2RequestBuilder struct {}
func (i *V2RequestBuilder) Query(key string, values ...matchers.Matcher) *V2RequestBuilder
func (i *V2RequestBuilder) Header(key string, values ...matchers.Matcher) *V2RequestBuilder
func (i *V2RequestBuilder) Headers(headers matchers.HeadersMatcher) *V2RequestBuilder
func (i *V2RequestBuilder) JSONBody(body interface{}) *V2RequestBuilder
func (i *V2RequestBuilder) BinaryBody(body []byte) *V2RequestBuilder
func (i *V2RequestBuilder) MultipartBody(contentType string, filename string, mimePartName string) *V2RequestBuilder
func (i *V2RequestBuilder) Body(contentType string, body []byte) *V2RequestBuilder
func (i *V2RequestBuilder) BodyMatch(body interface{}) *V2RequestBuilder
type V2ResponseBuilderFunc func(*V2ResponseBuilder)
type V2ResponseBuilder struct {}
func (i *V2ResponseBuilder) Header(key string, values ...matchers.Matcher) *V2ResponseBuilder
func (i *V2ResponseBuilder) Headers(headers matchers.HeadersMatcher) *V2ResponseBuilder
func (i *V2ResponseBuilder) JSONBody(body interface{}) *V2ResponseBuilder
func (i *V2ResponseBuilder) BinaryBody(body []byte) *V2ResponseBuilder
func (i *V2ResponseBuilder) MultipartBody(contentType string, filename string, mimePartName string) *V2ResponseBuilder
func (i *V2ResponseBuilder) Body(contentType string, body []byte) *V2ResponseBuilder
func (i *V2ResponseBuilder) BodyMatch(body interface{}) *V2ResponseBuilder
```

File: ./consumer/http.go
```
package consumer

type MockHTTPProviderConfig struct {
	Consumer               string
	Provider               string
	LogDir                 string
	PactDir                string
	Host                   string
	AllowedMockServerPorts string
	Port                   int
	ClientTimeout          time.Duration
	TLS                    bool
}
type MockServerConfig struct {
	Port      int
	Host      string
	TLSConfig *tls.Config
}
```

File: ./consumer/http_v4.go
```
package consumer

type V4HTTPMockProvider struct {}
func NewV4Pact(config MockHTTPProviderConfig) (*V4HTTPMockProvider, error)
func (p *V4HTTPMockProvider) AddInteraction() *V4UnconfiguredInteraction
type V4UnconfiguredInteraction struct {}
func (i *V4UnconfiguredInteraction) Given(state string) *V4UnconfiguredInteraction
func (i *V4UnconfiguredInteraction) GivenWithParameter(state models.ProviderState) *V4UnconfiguredInteraction
func (i *V4UnconfiguredInteraction) UponReceiving(description string) *V4UnconfiguredInteraction
func (i *V4UnconfiguredInteraction) WithCompleteRequest(request Request) *V4InteractionWithCompleteRequest
func (i *V4UnconfiguredInteraction) WithRequest(method Method, path string, builders ...V4RequestBuilderFunc) *V4InteractionWithRequest
func (i *V4UnconfiguredInteraction) WithRequestPathMatcher(method Method, path matchers.Matcher, builders ...V4RequestBuilderFunc) *V4InteractionWithRequest
type V4InteractionWithRequest struct {}
func (i *V4InteractionWithRequest) WillRespondWith(status int, builders ...V4ResponseBuilderFunc) *V4InteractionWithResponse
type V4InteractionWithCompleteRequest struct {}
func (i *V4InteractionWithCompleteRequest) WithCompleteResponse(response Response) *V4InteractionWithResponse
type V4RequestBuilder struct {}
type V4RequestBuilderFunc func(*V4RequestBuilder)
func (i *V4RequestBuilder) Query(key string, values ...matchers.Matcher) *V4RequestBuilder
func (i *V4RequestBuilder) Header(key string, values ...matchers.Matcher) *V4RequestBuilder
func (i *V4RequestBuilder) Headers(headers matchers.HeadersMatcher) *V4RequestBuilder
func (i *V4RequestBuilder) JSONBody(body interface{}) *V4RequestBuilder
func (i *V4RequestBuilder) BinaryBody(body []byte) *V4RequestBuilder
func (i *V4RequestBuilder) MultipartBody(contentType string, filename string, mimePartName string) *V4RequestBuilder
func (i *V4RequestBuilder) Body(contentType string, body []byte) *V4RequestBuilder
func (i *V4RequestBuilder) BodyMatch(body interface{}) *V4RequestBuilder
type V4ResponseBuilder struct {}
type V4ResponseBuilderFunc func(*V4ResponseBuilder)
type V4InteractionWithResponse struct {}
func (i *V4ResponseBuilder) Header(key string, values ...matchers.Matcher) *V4ResponseBuilder
func (i *V4ResponseBuilder) Headers(headers matchers.HeadersMatcher) *V4ResponseBuilder
func (i *V4ResponseBuilder) JSONBody(body interface{}) *V4ResponseBuilder
func (i *V4ResponseBuilder) BinaryBody(body []byte) *V4ResponseBuilder
func (i *V4ResponseBuilder) MultipartBody(contentType string, filename string, mimePartName string) *V4ResponseBuilder
```
