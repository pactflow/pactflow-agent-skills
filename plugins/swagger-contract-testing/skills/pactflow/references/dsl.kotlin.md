While you already know this, here is a reminder of the key pact-jvm Kotlin classes and methods you will need to use to create a Pact test in Kotlin (having omitted deprecated and implementation-detail members):

## HTTP Consumer DSL

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/ConsumerPactBuilder.kt

```kotlin
class ConsumerPactBuilder(
  /**
   * Returns the name of the consumer
   * @return consumer name
   */
  val consumerName: String
  ) {
    fun hasPactWith(provider: String): PactDslWithProvider
    fun pactSpecVersion(version: PactSpecVersion): ConsumerPactBuilder
    companion object {
        fun consumer(consumer: String): ConsumerPactBuilder
        fun jsonBody(): PactDslJsonBody
        fun xmlToString(body: Document): String
    }
}
```

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/dsl/PactDslWithProvider.kt

```kotlin
class PactDslWithProvider@JvmOverloads constructor(
  val consumerPactBuilder: ConsumerPactBuilder,
  private val providerName: String,
  val version: PactSpecVersion = PactSpecVersion.V3
) {
    fun given(state: String): PactDslWithState
    fun given(state: String, params: Map<String, Any?>): PactDslWithState
    fun given(state: String, firstKey: String, firstValue: Any?, vararg paramsKeyValuePair: Any): PactDslWithState
    fun uponReceiving(description: String): PactDslRequestWithoutPath
    fun setDefaultRequestValues(defaultRequestValues: PactDslRequestWithoutPath)
    fun setDefaultResponseValues(defaultResponseValues: PactDslResponse)
    fun addMetadataValue(key: String, value: String): PactDslWithProvider
    fun addMetadataValue(key: String, value: JsonValue): PactDslWithProvider
}
```

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/dsl/PactDslWithState.kt

```kotlin
class PactDslWithState@JvmOverloads constructor(
  private val consumerPactBuilder: ConsumerPactBuilder,
  var consumerName: String,
  var providerName: String,
  private val defaultRequestValues: PactDslRequestWithoutPath?,
  private val defaultResponseValues: PactDslResponse?,
  val version: PactSpecVersion = PactSpecVersion.V3,
  private var additionalMetadata: MutableMap<String, JsonValue> = mutableMapOf()
) {
    fun uponReceiving(description: String): PactDslRequestWithoutPath
    fun given(stateDesc: String): PactDslWithState
    fun given(stateDesc: String, params: Map<String, Any?>): PactDslWithState
    fun comment(comment: String): PactDslWithState
    fun addMetadataValue(key: String, value: String): PactDslWithState
    fun addMetadataValue(key: String, value: JsonValue): PactDslWithState
}
```

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/dsl/PactDslRequestWithoutPath.kt

```kotlin
class PactDslRequestWithoutPath@JvmOverloads constructor(
    private val consumerPactBuilder: ConsumerPactBuilder,
    private val pactDslWithState: PactDslWithState,
    private val description: String,
    defaultRequestValues: PactDslRequestWithoutPath?,
    private val defaultResponseValues: PactDslResponse?,
    version: PactSpecVersion = PactSpecVersion.V3,
    private val additionalMetadata: MutableMap<String, JsonValue>
) : PactDslRequestBase(defaultRequestValues, pactDslWithState.comments, version) {
    fun method(method: String): PactDslRequestWithoutPath
    fun headers(headers: Map<String, String>): PactDslRequestWithoutPath
    fun headers(
    firstHeaderName: String,
    firstHeaderValue: String,
    vararg headerNameValuePairs: String
  ): PactDslRequestWithoutPath
    fun query(query: String): PactDslRequestWithoutPath
    fun body(body: String): PactDslRequestWithoutPath
    fun body(body: String, contentType: String): PactDslRequestWithoutPath
    fun body(body: String, contentType: ContentType): PactDslRequestWithoutPath
    fun body(body: Supplier<String>): PactDslRequestWithoutPath
    fun body(body: Supplier<String>, contentType: String): PactDslRequestWithoutPath
    fun body(body: Supplier<String>, contentType: ContentType): PactDslRequestWithoutPath
    fun bodyWithSingleQuotes(body: String): PactDslRequestWithoutPath
    fun bodyWithSingleQuotes(body: String, contentType: String): PactDslRequestWithoutPath
    fun bodyWithSingleQuotes(body: String, contentType: ContentType): PactDslRequestWithoutPath
    fun body(body: JSONObject): PactDslRequestWithoutPath
    fun body(body: DslPart): PactDslRequestWithoutPath
    fun body(body: Document): PactDslRequestWithoutPath
    fun body(xmlBuilder: PactXmlBuilder): PactDslRequestWithoutPath
    fun body(body: MultipartEntityBuilder): PactDslRequestWithoutPath
    fun bodyMatchingContentType(contentType: String, exampleContents: String): PactDslRequestWithoutPath
    fun withBinaryData(example: ByteArray, contentType: String): PactDslRequestWithoutPath
    fun path(path: String): PactDslRequestWithPath
    fun path(
    path: String,
    addRequestMatchers: PactDslRequestWithPath.() -> PactDslRequestWithPath
  ): PactDslRequestWithPath
    fun matchPath(pathRegex: String, path: String = Random.generateRandomString(pathRegex)): PactDslRequestWithPath
    fun matchPath(
    pathRegex: String,
    path: String = Random.generateRandomString(pathRegex),
    addRequestMatchers: PactDslRequestWithPath.() -> PactDslRequestWithPath
  ): PactDslRequestWithPath
    fun withFileUpload(
    partName: String,
    fileName: String,
    fileContentType: String?,
    data: ByteArray
  ): PactDslRequestWithoutPath
    fun headerFromProviderState(name: String, expression: String, example: String): PactDslRequestWithoutPath
    fun queryParameterFromProviderState(name: String, expression: String, example: String): PactDslRequestWithoutPath
    fun pathFromProviderState(expression: String, example: String): PactDslRequestWithPath
    fun pathFromProviderState(
    expression: String,
    example: String,
    addRequestMatchers: PactDslRequestWithPath.() -> PactDslRequestWithPath
  ): PactDslRequestWithPath
    fun queryMatchingDate(field: String, pattern: String, example: String): PactDslRequestWithoutPath
    fun queryMatchingDate(field: String, pattern: String): PactDslRequestWithoutPath
    fun queryMatchingTime(field: String, pattern: String, example: String): PactDslRequestWithoutPath
    fun queryMatchingTime(field: String, pattern: String): PactDslRequestWithoutPath
    fun queryMatchingDatetime(field: String, pattern: String, example: String): PactDslRequestWithoutPath
    fun queryMatchingDatetime(field: String, pattern: String): PactDslRequestWithoutPath
    fun queryMatchingISODate(field: String, example: String? = null): PactDslRequestWithoutPath
    fun queryMatchingISOTime(field: String, example: String?): PactDslRequestWithoutPath
    fun queryMatchingTime(field: String): PactDslRequestWithoutPath
    fun queryMatchingISODatetime(field: String, example: String? = null): PactDslRequestWithoutPath
    fun addMetadataValue(key: String, value: String): PactDslRequestWithoutPath
    fun addMetadataValue(key: String, value: JsonValue): PactDslRequestWithoutPath
}
```

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/dsl/PactDslRequestWithPath.kt

```kotlin
class PactDslRequestWithPath : PactDslRequestBase {
    fun method(method: String): PactDslRequestWithPath
    fun headers(
    firstHeaderName: String,
    firstHeaderValue: String,
    vararg headerNameValuePairs: String
  ): PactDslRequestWithPath
    fun headers(headers: Map<String, String>): PactDslRequestWithPath
    fun query(query: String): PactDslRequestWithPath
    fun encodedQuery(query: String): PactDslRequestWithPath
    fun body(body: String): PactDslRequestWithPath
    fun body(body: String, contentType: String): PactDslRequestWithPath
    fun body(body: String, contentType: ContentType): PactDslRequestWithPath
    fun body(body: Supplier<String>): PactDslRequestWithPath
    fun body(body: Supplier<String>, contentType: String): PactDslRequestWithPath
    fun body(body: Supplier<String>, contentType: ContentType): PactDslRequestWithPath
    fun bodyWithSingleQuotes(body: String): PactDslRequestWithPath
    fun bodyWithSingleQuotes(body: String, contentType: String): PactDslRequestWithPath
    fun bodyWithSingleQuotes(body: String, contentType: ContentType): PactDslRequestWithPath
    fun body(body: JSONObject): PactDslRequestWithPath
    fun body(body: DslPart): PactDslRequestWithPath
    fun body(body: Document): PactDslRequestWithPath
    fun body(xmlBuilder: PactXmlBuilder): PactDslRequestWithPath
    fun body(body: MultipartEntityBuilder): PactDslRequestWithPath
    fun bodyMatchingContentType(contentType: String, exampleContents: String): PactDslRequestWithPath
    fun withBinaryData(example: ByteArray, contentType: String): PactDslRequestWithPath
    fun path(path: String): PactDslRequestWithPath
    fun matchPath(pathRegex: String, path: String = Random.generateRandomString(pathRegex)): PactDslRequestWithPath
    fun matchHeader(
    header: String,
    regex: String,
    headerExample: String = Random.generateRandomString(regex)
  ): PactDslRequestWithPath
    fun willRespondWith(): PactDslResponse
    fun willRespondWith(addResponseMatchers: PactDslResponse.() -> PactDslResponse): PactDslResponse
    fun matchQuery(
    parameter: String,
    regex: String,
    example: String = Random.generateRandomString(regex)
  ): PactDslRequestWithPath
    fun matchQuery(parameter: String, regex: String, example: List<String>): PactDslRequestWithPath
    fun withFileUpload(
    partName: String,
    fileName: String,
    fileContentType: String?,
    data: ByteArray
  ): PactDslRequestWithPath
    fun headerFromProviderState(name: String, expression: String, example: String): PactDslRequestWithPath
    fun queryParameterFromProviderState(name: String, expression: String, example: String): PactDslRequestWithPath
    fun pathFromProviderState(expression: String, example: String): PactDslRequestWithPath
    fun queryMatchingDate(field: String, pattern: String, example: String): PactDslRequestWithPath
    fun queryMatchingDate(field: String, pattern: String): PactDslRequestWithPath
    fun queryMatchingTime(field: String, pattern: String, example: String): PactDslRequestWithPath
    fun queryMatchingTime(field: String, pattern: String): PactDslRequestWithPath
    fun queryMatchingDatetime(field: String, pattern: String, example: String): PactDslRequestWithPath
    fun queryMatchingDatetime(field: String, pattern: String): PactDslRequestWithPath
    fun queryMatchingISODate(field: String, example: String? = null): PactDslRequestWithPath
    fun queryMatchingISOTime(field: String, example: String?): PactDslRequestWithPath
    fun queryMatchingTime(field: String): PactDslRequestWithPath
    fun queryMatchingISODatetime(field: String, example: String? = null): PactDslRequestWithPath
    fun body(builder: BodyBuilder): PactDslRequestWithPath
    fun comment(comment: String): PactDslRequestWithPath
    fun addMetadataValue(key: String, value: String): PactDslRequestWithPath
    fun addMetadataValue(key: String, value: JsonValue): PactDslRequestWithPath
}
```

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/dsl/PactDslResponse.kt

```kotlin
class PactDslResponse@JvmOverloads constructor(
    private val consumerPactBuilder: ConsumerPactBuilder,
    private val request: PactDslRequestWithPath?,
    private val defaultRequestValues: PactDslRequestWithoutPath? = null,
    private val defaultResponseValues: PactDslResponse? = null,
    private val comments: MutableList<String> = mutableListOf(),
    val version: PactSpecVersion = PactSpecVersion.V3,
    private val additionalMetadata: MutableMap<String, JsonValue> = mutableMapOf()
) {
    fun status(status: Int): PactDslResponse
    fun headers(headers: Map<String, String>): PactDslResponse
    fun body(body: String): PactDslResponse
    fun body(body: String, contentType: String): PactDslResponse
    fun body(body: String, contentType: ContentType): PactDslResponse
    fun body(body: Supplier<String>): PactDslResponse
    fun body(body: Supplier<String>, contentType: String): PactDslResponse
    fun body(body: Supplier<String>, contentType: ContentType): PactDslResponse
    fun bodyWithSingleQuotes(body: String): PactDslResponse
    fun bodyWithSingleQuotes(body: String, contentType: String): PactDslResponse
    fun bodyWithSingleQuotes(body: String, contentType: ContentType): PactDslResponse
    fun body(body: JSONObject): PactDslResponse
    fun body(body: DslPart): PactDslResponse
    fun body(body: Document): PactDslResponse
    fun body(builder: BodyBuilder): PactDslResponse
    fun withBinaryData(example: ByteArray, contentType: String): PactDslResponse
    fun matchHeader(header: String, regexp: String?, headerExample: String = Random.generateRandomString(regexp.orEmpty())): PactDslResponse
    fun toPact(pactClass: Class<P>): P
    fun toPact(): RequestResponsePact
    fun uponReceiving(description: String): PactDslRequestWithPath
    fun given(state: String): PactDslWithState
    fun given(state: String, params: Map<String, Any>): PactDslWithState
    fun headerFromProviderState(name: String, expression: String, example: String): PactDslResponse
    fun matchSetCookie(cookie: String, regex: String, example: String): PactDslResponse
    fun body(xmlBuilder: PactXmlBuilder): PactDslResponse
    fun comment(comment: String): PactDslResponse
    fun informationStatus(): PactDslResponse
    fun successStatus(): PactDslResponse
    fun redirectStatus(): PactDslResponse
    fun clientErrorStatus(): PactDslResponse
    fun serverErrorStatus(): PactDslResponse
    fun nonErrorStatus(): PactDslResponse
    fun errorStatus(): PactDslResponse
    fun statusCodes(statusCodes: List<Int>): PactDslResponse
    fun addMetadataValue(key: String, value: String): PactDslResponse
    fun addMetadataValue(key: String, value: JsonValue): PactDslResponse
    fun bodyMatchingContentType(contentType: String, exampleContents: String): PactDslResponse
}
```

## Body / Matching DSL

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/dsl/PactDslJsonBody.kt

```kotlin
class PactDslJsonBody : DslPart {
    fun stringValue(name: String, vararg values: String?): PactDslJsonBody
    fun numberValue(name: String, vararg values: Number): PactDslJsonBody
    fun booleanValue(name: String, vararg values: Boolean?): PactDslJsonBody
    fun like(name: String, vararg examples: Any?): PactDslJsonBody
    fun stringType(name: String): PactDslJsonBody
    fun stringTypes(vararg names: String?): PactDslJsonBody
    fun stringType(name: String, vararg examples: String?): PactDslJsonBody
    fun numberType(name: String): PactDslJsonBody
    fun numberTypes(vararg names: String?): PactDslJsonBody
    fun numberType(name: String, vararg numbers: Number?): PactDslJsonBody
    fun integerType(name: String): PactDslJsonBody
    fun integerTypes(vararg names: String?): PactDslJsonBody
    fun integerType(name: String, vararg numbers: Long?): PactDslJsonBody
    fun integerType(name: String, vararg numbers: Int?): PactDslJsonBody
    fun decimalType(name: String): PactDslJsonBody
    fun decimalTypes(vararg names: String?): PactDslJsonBody
    fun decimalType(name: String, vararg numbers: BigDecimal?): PactDslJsonBody
    fun decimalType(name: String, vararg numbers: Double?): PactDslJsonBody
    fun numberMatching(name: String, regex: String, example: Number): PactDslJsonBody
    fun decimalMatching(name: String, regex: String, example: Double): PactDslJsonBody
    fun integerMatching(name: String, regex: String, example: Int): PactDslJsonBody
    fun booleanTypes(vararg names: String?): PactDslJsonBody
    fun booleanType(name: String, vararg examples: Boolean? = arrayOf(true)): PactDslJsonBody
    fun stringMatcher(name: String, regex: String, vararg values: String?): PactDslJsonBody
    fun stringMatcher(name: String, regex: String): PactDslJsonBody
    fun datetime(name: String): PactDslJsonBody
    fun datetime(name: String, format: String): PactDslJsonBody
    fun datetime(
    name: String,
    format: String,
    example: Date,
    timeZone: TimeZone = TimeZone.getDefault()
  )
    fun datetime(
    name: String,
    format: String,
    timeZone: TimeZone = TimeZone.getDefault(),
    vararg examples: Date
  ): PactDslJsonBody
    fun datetime(
    name: String,
    format: String,
    example: Instant,
    timeZone: TimeZone = TimeZone.getDefault()
  )
    fun datetime(
    name: String,
    format: String,
    timeZone: TimeZone = TimeZone.getDefault(),
    vararg examples: Instant
  ): PactDslJsonBody
    fun date(name: String = "date"): PactDslJsonBody
    fun date(name: String, format: String): PactDslJsonBody
    fun date(name: String, format: String, example: Date, timeZone: TimeZone = TimeZone.getDefault())
    fun date(
    name: String,
    format: String,
    timeZone: TimeZone = TimeZone.getDefault(),
    vararg examples: Date
  ): PactDslJsonBody
    fun localDate(name: String, format: String, vararg examples: LocalDate): PactDslJsonBody
    fun time(name: String = "time"): PactDslJsonBody
    fun time(name: String, format: String): PactDslJsonBody
    fun time(
    name: String,
    format: String,
    example: Date,
    timeZone: TimeZone = TimeZone.getDefault()
  )
    fun time(
    name: String,
    format: String,
    timeZone: TimeZone = TimeZone.getDefault(),
    vararg examples: Date
  ): PactDslJsonBody
    fun ipAddress(name: String): PactDslJsonBody
    fun `object`(name: String): PactDslJsonBody
    fun `object`(): PactDslJsonBody
    fun `object`(name: String, value: DslPart): PactDslJsonBody
    fun closeObject(): DslPart?
    fun close(): DslPart?
    fun array(name: String): PactDslJsonArray
    fun array(): PactDslJsonArray
    fun unorderedArray(name: String): PactDslJsonArray
    fun unorderedArray(): PactDslJsonArray
    fun unorderedMinArray(name: String, size: Int): PactDslJsonArray
    fun unorderedMinArray(size: Int): PactDslJsonArray
    fun unorderedMaxArray(name: String, size: Int): PactDslJsonArray
    fun unorderedMaxArray(size: Int): PactDslJsonArray
    fun unorderedMinMaxArray(name: String, minSize: Int, maxSize: Int): PactDslJsonArray
    fun unorderedMinMaxArray(minSize: Int, maxSize: Int): PactDslJsonArray
    fun closeArray(): DslPart?
    fun eachLike(name: String): PactDslJsonBody
    fun eachLike(name: String, obj: DslPart): PactDslJsonBody
    fun eachLike(): PactDslJsonBody
    fun eachLike(obj: DslPart): PactDslJsonArray
    fun eachLike(name: String, numberExamples: Int): PactDslJsonBody
    fun eachLike(numberExamples: Int): PactDslJsonBody
    fun eachLike(name: String, value: PactDslJsonRootValue, numberExamples: Int = 1): PactDslJsonBody
    fun minArrayLike(name: String, size: Int): PactDslJsonBody
    fun minArrayLike(size: Int): PactDslJsonBody
    fun minArrayLike(name: String, size: Int, obj: DslPart): PactDslJsonBody
    fun minArrayLike(size: Int, obj: DslPart): PactDslJsonArray
    fun minArrayLike(name: String, size: Int, numberExamples: Int): PactDslJsonBody
    fun minArrayLike(size: Int, numberExamples: Int): PactDslJsonBody
    fun minArrayLike(name: String, size: Int, value: PactDslJsonRootValue, numberExamples: Int = 2): PactDslJsonBody
    fun minArrayLike(name: String, size: Int, value: DslPart, numberExamples: Int): PactDslJsonBody
    fun maxArrayLike(name: String, size: Int): PactDslJsonBody
    fun maxArrayLike(size: Int): PactDslJsonBody
    fun maxArrayLike(name: String, size: Int, obj: DslPart): PactDslJsonBody
    fun maxArrayLike(size: Int, obj: DslPart): PactDslJsonArray
    fun maxArrayLike(name: String, size: Int, numberExamples: Int): PactDslJsonBody
    fun maxArrayLike(size: Int, numberExamples: Int): PactDslJsonBody
    fun maxArrayLike(name: String, size: Int, value: PactDslJsonRootValue, numberExamples: Int = 1): PactDslJsonBody
    fun maxArrayLike(name: String, size: Int, value: DslPart, numberExamples: Int): PactDslJsonBody
    fun id(name: String = "id"): PactDslJsonBody
    fun id(name: String, vararg examples: Long): PactDslJsonBody
    fun hexValue(name: String): PactDslJsonBody
    fun hexValue(name: String, vararg examples: String): PactDslJsonBody
    fun uuid(name: String): PactDslJsonBody
    fun uuid(name: String, vararg uuids: UUID): PactDslJsonBody
    fun uuid(name: String, vararg examples: String): PactDslJsonBody
    fun nullValue(fieldName: String): PactDslJsonBody
    fun eachArrayLike(name: String): PactDslJsonArray
    fun eachArrayLike(): PactDslJsonArray
    fun eachArrayLike(name: String, numberExamples: Int): PactDslJsonArray
    fun eachArrayLike(numberExamples: Int): PactDslJsonArray
    fun eachArrayWithMaxLike(name: String, size: Int): PactDslJsonArray
    fun eachArrayWithMaxLike(size: Int): PactDslJsonArray
    fun eachArrayWithMaxLike(name: String, numberExamples: Int, size: Int): PactDslJsonArray
    fun eachArrayWithMaxLike(numberExamples: Int, size: Int): PactDslJsonArray
    fun eachArrayWithMinLike(name: String, size: Int): PactDslJsonArray
    fun eachArrayWithMinLike(size: Int): PactDslJsonArray
    fun eachArrayWithMinLike(name: String, numberExamples: Int, size: Int): PactDslJsonArray
    fun eachArrayWithMinLike(numberExamples: Int, size: Int): PactDslJsonArray
    fun eachKeyMappedToAnArrayLike(exampleKey: String): PactDslJsonBody
    fun eachKeyLike(exampleKey: String): PactDslJsonBody
    fun eachKeyLike(exampleKey: String, value: PactDslJsonRootValue): PactDslJsonBody
    fun eachValueLike(exampleKey: String): PactDslJsonBody
    fun eachValueLike(exampleKey: String, value: PactDslJsonRootValue): PactDslJsonBody
    fun includesStr(name: String, value: String): PactDslJsonBody
    fun equalTo(name: String, vararg examples: Any?): PactDslJsonBody
    fun and(name: String, value: Any?, vararg rules: MatchingRule): PactDslJsonBody
    fun or(name: String, value: Any?, vararg rules: MatchingRule): PactDslJsonBody
    fun matchUrl(name: String, basePath: String?, vararg pathFragments: Any): PactDslJsonBody
    fun matchUrl(basePath: String?, vararg pathFragments: Any): DslPart
    fun matchUrl2(name: String, vararg pathFragments: Any): PactDslJsonBody
    fun matchUrl2(vararg pathFragments: Any): DslPart
    fun minMaxArrayLike(name: String, minSize: Int, maxSize: Int): PactDslJsonBody
    fun minMaxArrayLike(name: String, minSize: Int, maxSize: Int, obj: DslPart): PactDslJsonBody
    fun minMaxArrayLike(minSize: Int, maxSize: Int): PactDslJsonBody
    fun minMaxArrayLike(minSize: Int, maxSize: Int, obj: DslPart): PactDslJsonArray
    fun minMaxArrayLike(name: String, minSize: Int, maxSize: Int, numberExamples: Int): PactDslJsonBody
    fun minMaxArrayLike(minSize: Int, maxSize: Int, numberExamples: Int): PactDslJsonBody
    fun eachArrayWithMinMaxLike(name: String, minSize: Int, maxSize: Int): PactDslJsonArray
    fun eachArrayWithMinMaxLike(minSize: Int, maxSize: Int): PactDslJsonArray
    fun eachArrayWithMinMaxLike(
    name: String,
    numberExamples: Int,
    minSize: Int,
    maxSize: Int
  ): PactDslJsonArray
    fun eachArrayWithMinMaxLike(numberExamples: Int, minSize: Int, maxSize: Int): PactDslJsonArray
    fun minMaxArrayLike(
    name: String,
    minSize: Int,
    maxSize: Int,
    value: PactDslJsonRootValue,
    numberExamples: Int
  ): PactDslJsonBody
    fun minMaxArrayLike(
    name: String,
    minSize: Int,
    maxSize: Int,
    value: DslPart,
    numberExamples: Int
  ): PactDslJsonBody
    fun valueFromProviderState(name: String, expression: String, example: Any?): PactDslJsonBody
    fun dateExpression(
    name: String,
    expression: String,
    format: String = DateFormatUtils.ISO_DATE_FORMAT.pattern
  ): PactDslJsonBody
    fun timeExpression(
    name: String,
    expression: String,
    format: String = DateFormatUtils.ISO_TIME_NO_T_FORMAT.pattern
  ): PactDslJsonBody
    fun datetimeExpression(
    name: String,
    expression: String,
    format: String = DateFormatUtils.ISO_DATETIME_FORMAT.pattern
  ): PactDslJsonBody
    fun arrayContaining(name: String): DslPart
    fun extendFrom(baseTemplate: PactDslJsonBody)
    fun eachKeyMatching(matcher: Matcher): PactDslJsonBody
    fun eachValueMatching(exampleKey: String): PactDslJsonBody
}
```

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/dsl/PactDslJsonArray.kt

```kotlin
class PactDslJsonArray : DslPart {
    fun closeArray(): DslPart?
    fun eachLike(name: String): PactDslJsonBody
    fun eachLike(name: String, obj: DslPart): PactDslJsonBody
    fun eachLike(name: String, numberExamples: Int): PactDslJsonBody
    fun eachLike(): PactDslJsonBody
    fun eachLike(obj: DslPart): PactDslJsonArray
    fun eachLike(numberExamples: Int): PactDslJsonBody
    fun minArrayLike(name: String, size: Int): PactDslJsonBody
    fun minArrayLike(size: Int): PactDslJsonBody
    fun minArrayLike(name: String, size: Int, obj: DslPart): PactDslJsonBody
    fun minArrayLike(size: Int, obj: DslPart): PactDslJsonArray
    fun minArrayLike(name: String, size: Int, numberExamples: Int): PactDslJsonBody
    fun minArrayLike(size: Int, numberExamples: Int): PactDslJsonBody
    fun maxArrayLike(name: String, size: Int): PactDslJsonBody
    fun maxArrayLike(size: Int): PactDslJsonBody
    fun maxArrayLike(name: String, size: Int, obj: DslPart): PactDslJsonBody
    fun maxArrayLike(size: Int, obj: DslPart): PactDslJsonArray
    fun maxArrayLike(name: String, size: Int, numberExamples: Int): PactDslJsonBody
    fun maxArrayLike(size: Int, numberExamples: Int): PactDslJsonBody
    fun stringValue(value: String?): PactDslJsonArray
    fun string(value: String?): PactDslJsonArray
    fun numberValue(value: Number): PactDslJsonArray
    fun number(value: Number): PactDslJsonArray
    fun booleanValue(value: Boolean): PactDslJsonArray
    fun like(example: Any?): PactDslJsonArray
    fun stringType(): PactDslJsonArray
    fun stringType(example: String): PactDslJsonArray
    fun numberType(): PactDslJsonArray
    fun numberType(number: Number): PactDslJsonArray
    fun integerType(): PactDslJsonArray
    fun integerType(number: Long): PactDslJsonArray
    fun decimalType(): PactDslJsonArray
    fun decimalType(number: BigDecimal): PactDslJsonArray
    fun decimalType(number: Double): PactDslJsonArray
    fun numberMatching(regex: String, example: Number): PactDslJsonArray
    fun decimalMatching(regex: String, example: Double): PactDslJsonArray
    fun integerMatching(regex: String, example: Int): PactDslJsonArray
    fun booleanType(): PactDslJsonArray
    fun booleanType(example: Boolean): PactDslJsonArray
    fun stringMatcher(regex: String, value: String): PactDslJsonArray
    fun datetime(): PactDslJsonArray
    fun datetime(format: String): PactDslJsonArray
    fun datetime(format: String, example: Date): PactDslJsonArray
    fun datetime(format: String, example: Instant): PactDslJsonArray
    fun date(): PactDslJsonArray
    fun date(format: String): PactDslJsonArray
    fun date(format: String, example: Date): PactDslJsonArray
    fun time(): PactDslJsonArray
    fun time(format: String): PactDslJsonArray
    fun time(format: String, example: Date): PactDslJsonArray
    fun ipAddress(): PactDslJsonArray
    fun `object`(name: String): PactDslJsonBody
    fun `object`(): PactDslJsonBody
    fun closeObject(): DslPart?
    fun close(): DslPart?
    fun arrayContaining(name: String): DslPart
    fun array(name: String): PactDslJsonArray
    fun array(): PactDslJsonArray
    fun unorderedArray(name: String): PactDslJsonArray
    fun unorderedArray(): PactDslJsonArray
    fun unorderedMinArray(name: String, size: Int): PactDslJsonArray
    fun unorderedMinArray(size: Int): PactDslJsonArray
    fun unorderedMaxArray(name: String, size: Int): PactDslJsonArray
    fun unorderedMaxArray(size: Int): PactDslJsonArray
    fun unorderedMinMaxArray(name: String, minSize: Int, maxSize: Int): PactDslJsonArray
    fun unorderedMinMaxArray(minSize: Int, maxSize: Int): PactDslJsonArray
    fun wildcardArrayMatcher(rule: MatchingRule): PactDslJsonArray
    fun id(): PactDslJsonArray
    fun id(id: Long): PactDslJsonArray
    fun hexValue(): PactDslJsonArray
    fun hexValue(hexValue: String): PactDslJsonArray
    fun uuid(): PactDslJsonArray
    fun uuid(uuid: String): PactDslJsonArray
    fun template(template: DslPart): PactDslJsonArray
    fun template(template: DslPart, occurrences: Int): PactDslJsonArray
    fun nullValue(): PactDslJsonArray
    fun eachArrayLike(name: String): PactDslJsonArray
    fun eachArrayLike(name: String, numberExamples: Int): PactDslJsonArray
    fun eachArrayLike(): PactDslJsonArray
    fun eachArrayLike(numberExamples: Int): PactDslJsonArray
    fun eachArrayWithMaxLike(name: String, size: Int): PactDslJsonArray
    fun eachArrayWithMaxLike(name: String, numberExamples: Int, size: Int): PactDslJsonArray
    fun eachArrayWithMaxLike(size: Int): PactDslJsonArray
    fun eachArrayWithMaxLike(numberExamples: Int, size: Int): PactDslJsonArray
    fun eachArrayWithMinLike(name: String, size: Int): PactDslJsonArray
    fun eachArrayWithMinLike(name: String, numberExamples: Int, size: Int): PactDslJsonArray
    fun eachArrayWithMinLike(size: Int): PactDslJsonArray
    fun eachArrayWithMinLike(numberExamples: Int, size: Int): PactDslJsonArray
    fun eachLike(value: PactDslJsonRootValue?, numberExamples: Int = 1): PactDslJsonArray
    fun minArrayLike(size: Int, value: PactDslJsonRootValue?, numberExamples: Int = size): PactDslJsonArray
    fun maxArrayLike(size: Int, value: PactDslJsonRootValue?, numberExamples: Int = 1): PactDslJsonArray
    fun includesStr(value: String): PactDslJsonArray
    fun equalsTo(value: Any?): PactDslJsonArray
    fun and(value: Any?, vararg rules: MatchingRule): PactDslJsonArray
    fun or(value: Any?, vararg rules: MatchingRule): PactDslJsonArray
    fun matchUrl(basePath: String?, vararg pathFragments: Any): PactDslJsonArray
    fun matchUrl(name: String, basePath: String?, vararg pathFragments: Any): DslPart
    fun matchUrl2(name: String, vararg pathFragments: Any): PactDslJsonBody
    fun matchUrl2(vararg pathFragments: Any): DslPart
    fun minMaxArrayLike(name: String, minSize: Int, maxSize: Int): PactDslJsonBody
    fun minMaxArrayLike(name: String, minSize: Int, maxSize: Int, obj: DslPart): PactDslJsonBody
    fun minMaxArrayLike(minSize: Int, maxSize: Int): PactDslJsonBody
    fun minMaxArrayLike(minSize: Int, maxSize: Int, obj: DslPart): PactDslJsonArray
    fun minMaxArrayLike(name: String, minSize: Int, maxSize: Int, numberExamples: Int): PactDslJsonBody
    fun minMaxArrayLike(minSize: Int, maxSize: Int, numberExamples: Int): PactDslJsonBody
    fun eachArrayWithMinMaxLike(name: String, minSize: Int, maxSize: Int): PactDslJsonArray
    fun eachArrayWithMinMaxLike(minSize: Int, maxSize: Int): PactDslJsonArray
    fun eachArrayWithMinMaxLike(
    name: String,
    numberExamples: Int,
    minSize: Int,
    maxSize: Int
  ): PactDslJsonArray
    fun eachArrayWithMinMaxLike(numberExamples: Int, minSize: Int, maxSize: Int): PactDslJsonArray
    fun valueFromProviderState(expression: String?, example: Any?): PactDslJsonArray
    fun dateExpression(expression: String, format: String = DateFormatUtils.ISO_DATE_FORMAT.pattern): PactDslJsonArray
    fun timeExpression(
    expression: String,
    format: String = DateFormatUtils.ISO_TIME_NO_T_FORMAT.pattern
  ): PactDslJsonArray
    fun datetimeExpression(
    expression: String,
    format: String = DateFormatUtils.ISO_DATETIME_FORMAT.pattern
  ): PactDslJsonArray
}
```

## Message Consumer DSL

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/MessagePactBuilder.kt

```kotlin
class MessagePactBuilder@JvmOverloads constructor(
  /**
   * The consumer for the pact.
   */
  private var consumer: Consumer = Consumer(),

  /**
   * The provider for the pact.
   */
  private var provider: Provider = Provider(),

  /**
   * Provider states
   */
  private var providerStates: MutableList<ProviderState> = mutableListOf(),

  /**
   * Messages for the pact
   */
  private var messages: MutableList<V4Interaction.AsynchronousMessage> = mutableListOf(),

  /**
   * Specification Version
   */
  private var specVersion: PactSpecVersion = PactSpecVersion.V3
) {
    fun consumer(consumer: String): MessagePactBuilder
    fun hasPactWith(provider: String): MessagePactBuilder
    fun given(providerState: String): MessagePactBuilder
    fun given(providerState: String, params: Map<String, Any>): MessagePactBuilder
    fun given(providerState: ProviderState): MessagePactBuilder
    fun expectsToReceive(description: String): MessagePactBuilder
    fun withMetadata(metadata: Map<String, Any>): MessagePactBuilder
    fun withMetadata(consumer: java.util.function.Consumer<MetadataBuilder>): MessagePactBuilder
    fun withContent(body: DslPart): MessagePactBuilder
    fun withContent(xmlBuilder: PactXmlBuilder): MessagePactBuilder
    fun withContent(contents: String, contentType: String = "text/plain"): MessagePactBuilder
    fun withContent(json: JSONObject): MessagePactBuilder
    fun toPact(pactClass: Class<P>): P
    fun toPact(): P
}
```

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/dsl/SynchronousMessagePactBuilder.kt

```kotlin
class SynchronousMessagePactBuilder@JvmOverloads constructor(
  /**
   * The consumer for the pact.
   */
  private var consumer: Consumer = Consumer(),

  /**
   * The provider for the pact.
   */
  private var provider: Provider = Provider(),

  /**
   * Provider states
   */
  private var providerStates: MutableList<ProviderState> = mutableListOf(),

  /**
   * Interactions for the pact
   */
  private var messages: MutableList<V4Interaction.SynchronousMessages> = mutableListOf(),

  /**
   * Specification Version
   */
  private var specVersion: PactSpecVersion = PactSpecVersion.V4
) {
    fun consumer(consumer: String): SynchronousMessagePactBuilder
    fun hasPactWith(provider: String): SynchronousMessagePactBuilder
    fun given(providerState: String): SynchronousMessagePactBuilder
    fun given(providerState: String, params: Map<String, Any>): SynchronousMessagePactBuilder
    fun given(providerState: ProviderState): SynchronousMessagePactBuilder
    fun pending(pending: Boolean): SynchronousMessagePactBuilder
    fun comment(comment: String): SynchronousMessagePactBuilder
    fun key(key: String?): SynchronousMessagePactBuilder
    fun expectsToReceive(description: String): SynchronousMessagePactBuilder
    fun withRequest(callback: java.util.function.Consumer<MessageContentsBuilder>): SynchronousMessagePactBuilder
    fun withResponse(callback: java.util.function.Consumer<MessageContentsBuilder>): SynchronousMessagePactBuilder
    fun toPact(pactClass: Class<P>): P
    fun toPact(): V4Pact
}
```

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/dsl/SynchronousMessageInteractionBuilder.kt

```kotlin
class SynchronousMessageInteractionBuilder(
  description: String,
  providerStates: MutableList<ProviderState>,
  comments: MutableList<JsonValue.StringValue>
) {
    fun key(key: String?): SynchronousMessageInteractionBuilder
    fun description(description: String): SynchronousMessageInteractionBuilder
    fun state(stateDescription: String, params: Map<String, Any?> = emptyMap()): SynchronousMessageInteractionBuilder
    fun state(stateDescription: String, paramKey: String, paramValue: Any?): SynchronousMessageInteractionBuilder
    fun state(stateDescription: String, vararg params: Pair<String, Any?>): SynchronousMessageInteractionBuilder
    fun pending(pending: Boolean): SynchronousMessageInteractionBuilder
    fun comment(comment: String): SynchronousMessageInteractionBuilder
    fun withRequest(
    builderFn: (MessageContentsBuilder) -> MessageContentsBuilder?
  ): SynchronousMessageInteractionBuilder
    fun willRespondWith(
    builderFn: (MessageContentsBuilder) -> MessageContentsBuilder?
  ): SynchronousMessageInteractionBuilder
    fun build(): V4Interaction
}
```

## V4 Pact Builder

File: ./consumer/src/main/kotlin/au/com/dius/pact/consumer/dsl/PactBuilder.kt

```kotlin
interface DslBuilder {
    fun addPluginConfiguration(matcher: ContentMatcher, pactConfiguration: Map<String, JsonValue>)
}

interface PluginInteractionBuilder {
    fun build(): Map<String, Any?>
}

class PactBuilder(
  var consumer: String = "consumer",
  var provider: String = "provider",
  var pactVersion: PactSpecVersion = PactSpecVersion.V4
) : DslBuilder {
    fun usingLegacyDsl(): PactDslWithProvider
    fun usingLegacyMessageDsl(): MessagePactBuilder
    fun usingSynchronousMessageDsl(): SynchronousMessagePactBuilder
    fun pactSpecVersion(version: PactSpecVersion)
    fun usingPlugin(name: String, version: String? = null): PactBuilder
    fun given(state: String, params: Map<String, Any?> = emptyMap()): PactBuilder
    fun given(state: String, firstKey: String, firstValue: Any?, vararg paramsKeyValuePair: Any): PactBuilder
    fun given(state: String, vararg params: Pair<String, Any>): PactBuilder
    fun expectsToReceive(description: String, interactionType: String, key: String? = null): PactBuilder
    fun with(values: Map<String, Any?>): PactBuilder
    fun with(builder: PluginInteractionBuilder): PactBuilder
    fun addPluginConfiguration(matcher: ContentMatcher, pactConfiguration: Map<String, JsonValue>)
    fun addMetadataValue(key: String, value: String): PactBuilder
    fun addMetadataValue(key: String, value: JsonValue): PactBuilder
    fun toPact(): V4Pact
    fun comment(comment: String): PactBuilder
    fun expectsToReceiveHttpInteraction(
    description: String,
    builderFn: (HttpInteractionBuilder) -> HttpInteractionBuilder?
  ): PactBuilder
    fun expectsToReceiveMessageInteraction(
    description: String,
    builderFn: (MessageInteractionBuilder) -> MessageInteractionBuilder?
  ): PactBuilder
    fun expectsToReceiveSynchronousMessageInteraction(
    description: String,
    builderFn: (SynchronousMessageInteractionBuilder) -> SynchronousMessageInteractionBuilder?
  ): PactBuilder
}
```

## JUnit 5 Consumer Annotations

File: ./consumer/junit5/src/main/kotlin/au/com/dius/pact/consumer/junit5/PactTestFor.kt

```kotlin
annotation class PactTestFor(
        /**
         * Providers name. This will be recorded in the pact file
         */
        val providerName: String = "",

        /**
         * Host interface to use for the mock server. Only used for synchronous provider tests and defaults to the
         * loopback adapter (127.0.0.1).
         */
        @Deprecated("This has been replaced with the @MockServerConfig annotation")
        val hostInterface: String = "",

        /**
         * Port number to bind to. Only used for synchronous provider tests and defaults to 0, which causes a random free port to be chosen.
         */
        @Deprecated("This has been replaced with the @MockServerConfig annotation")
        val port: String = "",

        /**
         * Pact specification version to support. Will default to V3.
         */
        val pactVersion: PactSpecVersion = PactSpecVersion.UNSPECIFIED,

        /**
         * Test method that provides the Pact to use for the test. Default behaviour is to use the first one found.
         */
        val pactMethod: String = "",

        /**
         * Type of provider (synchronous HTTP or asynchronous messages)
         */
        val providerType: ProviderType = ProviderType.UNSPECIFIED,

        /**
         * If HTTPS should be used. If enabled, a mock server with a self-signed cert will be started.
         */
        @Deprecated("This has been replaced with the @MockServerConfig annotation")
        val https: Boolean = false,

        /**
         * Test methods that provides the Pacts to use for the test. This allows multiple providers to be
         * used in the same test.
         */
        val pactMethods: Array<String> = [],

        /**
         * If an external keystore should be provided to the mockServer. This allos to provide a path to
         * keystore file
         */
        @Deprecated("This has been replaced with the @MockServerConfig annotation")
        val keyStorePath: String = "",

        /**
         * This property allows to provide the alias name of the certificate should be used.
         */
        @Deprecated("This has been replaced with the @MockServerConfig annotation")
        val keyStoreAlias: String = "",

        /**
         * This property allows to provide the password for the keystore
         */
        @Deprecated("This has been replaced with the @MockServerConfig annotation")
        val keyStorePassword: String = "",

        /**
         * This property allows to provide the password for the private key entry in the keystore
         */
        @Deprecated("This has been replaced with the @MockServerConfig annotation")
        val privateKeyPassword: String = "",

        /**
         * * The type of mock server implementation to use. The default is to use the Java server for HTTP and the KTor
         * server for HTTPS
         */
        @Deprecated("This has been replaced with the @MockServerConfig annotation")
        val mockServerImplementation: MockServerImplementation = MockServerImplementation.Default
)
```

## Provider Annotations & Verification

File: ./provider/src/main/kotlin/au/com/dius/pact/provider/junitsupport/Provider.kt

```kotlin
annotation class Provider(
  /**
   * @return provider name for pact test running
   */
  val value: String = ""
)
```

File: ./provider/src/main/kotlin/au/com/dius/pact/provider/junitsupport/Consumer.kt

```kotlin
annotation class Consumer(
  /**
   * @return consumer name for pact test running
   */
  val value: String = ""
)
```

File: ./provider/junit5/src/main/kotlin/au/com/dius/pact/provider/junit5/PactVerificationContext.kt

```kotlin
class PactVerificationContext@JvmOverloads constructor(
  private val store: ExtensionContext.Store,
  private val context: ExtensionContext,
  var target: TestTarget = HttpTestTarget(port = 8080),
  var verifier: IProviderVerifier? = null,
  var valueResolver: ValueResolver = SystemPropertyResolver,
  var providerInfo: IProviderInfo,
  val consumer: IConsumerInfo,
  val interaction: Interaction,
  val pact: Pact,
  var testExecutionResult: MutableList<VerificationResult.Failed> = mutableListOf(),
  val additionalTargets: MutableList<TestTarget> = mutableListOf()
) {
    fun verifyInteraction()
    fun withStateChangeHandlers(vararg stateClasses: Any): PactVerificationContext
    fun addStateChangeHandlers(vararg stateClasses: Any)
    fun addAdditionalTarget(target: TestTarget)
    fun currentTarget(): TestTarget?
}
```

Classes: Any): PactVerificationContext
    fun addStateChangeHandlers(vararg stateClasses: Any)
    fun addAdditionalTarget(target: TestTarget)
    fun currentTarget(): TestTarget?
}
```
