While you already know this, here is a reminder of the Pact-JVM classes and methods you will need to use to create a Pact test in Java (having omitted deprecated and unadvised methods):

```java
class LambdaDslJsonBody:
    fn build() -> DslPart
class LambdaDsl:
    fn newJsonArray(array: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn newJsonArrayMinLike(size: Integer, array: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn newJsonArrayMaxLike(size: Integer, array: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn newJsonArrayMinMaxLike(minSize: Integer, maxSize: Integer, array: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn newJsonArrayUnordered(array: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn newJsonArrayMinUnordered(size: int, array: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn newJsonArrayMaxUnordered(size: int, array: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn newJsonArrayMinMaxUnordered(minSize: int, maxSize: int, array: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn newJsonBody(array: Consumer<LambdaDslJsonBody>) -> LambdaDslJsonBody
public interface BodyBuilder:
    fn getMatchers() -> MatchingRuleCategory
    fn getGenerators() -> Generators
    fn getContentType() -> ContentType
    fn buildBody() -> byte[]
    fn getHeaderMatchers() -> MatchingRuleCategory
class LambdaDslObject:
    fn getPactDslObject() -> PactDslJsonBody
    fn stringValue(name: String, value: String) -> LambdaDslObject
    fn stringType(name: String, example: String) -> LambdaDslObject
    fn stringType(name: String) -> LambdaDslObject
    fn stringType(names: String...) -> LambdaDslObject
    fn stringMatcher(name: String, regex: String) -> LambdaDslObject
    fn stringMatcher(name: String, regex: String, example: String) -> LambdaDslObject
    fn numberValue(name: String, value: Number) -> LambdaDslObject
    fn numberType(name: String, example: Number) -> LambdaDslObject
    fn numberType(names: String...) -> LambdaDslObject
    fn integerType(name: String, example: Integer) -> LambdaDslObject
    fn integerType(names: String...) -> LambdaDslObject
    fn decimalType(name: String, example: BigDecimal) -> LambdaDslObject
    fn decimalType(name: String, example: Double) -> LambdaDslObject
    fn decimalType(names: String...) -> LambdaDslObject
    fn numberMatching(name: String, regex: String, example: Number) -> LambdaDslObject
    fn decimalMatching(name: String, regex: String, example: Double) -> LambdaDslObject
    fn integerMatching(name: String, regex: String, example: Integer) -> LambdaDslObject
    fn booleanValue(name: String, value: Boolean) -> LambdaDslObject
    fn booleanType(name: String, example: Boolean) -> LambdaDslObject
    fn booleanType(names: String...) -> LambdaDslObject
    fn id() -> LambdaDslObject
    fn id(name: String) -> LambdaDslObject
    fn id(name: String, example: Long) -> LambdaDslObject
    fn uuid(name: String) -> LambdaDslObject
    fn uuid(name: String, example: UUID) -> LambdaDslObject
    fn date() -> LambdaDslObject
    fn date(name: String) -> LambdaDslObject
    fn date(name: String, format: String) -> LambdaDslObject
    fn date(name: String, format: String, example: Date) -> LambdaDslObject
    fn date(name: String, format: String, example: Date, timeZone: TimeZone) -> LambdaDslObject
    fn date(name: String, format: String, example: ZonedDateTime) -> LambdaDslObject
    fn date(name: String, format: String, example: LocalDate) -> LambdaDslObject
    fn time() -> LambdaDslObject
    fn time(name: String) -> LambdaDslObject
    fn time(name: String, format: String) -> LambdaDslObject
    fn time(name: String, format: String, example: Date) -> LambdaDslObject
    fn time(name: String, format: String, example: Date, timeZone: TimeZone) -> LambdaDslObject
    fn time(name: String, format: String, example: ZonedDateTime) -> LambdaDslObject
    fn datetime(name: String, format: String) -> LambdaDslObject
    fn datetime(name: String, format: String, example: Date) -> LambdaDslObject
    fn datetime(name: String, format: String, example: Instant) -> LambdaDslObject
    fn datetime(name: String, format: String, example: Date, timeZone: TimeZone) -> LambdaDslObject
    fn datetime(name: String, format: String, example: ZonedDateTime) -> LambdaDslObject
    fn ipV4Address(name: String) -> LambdaDslObject
    fn valueFromProviderState(name: String, expression: String, example: Object) -> LambdaDslObject
    fn and(name: String, value: Object, rules: MatchingRule...) -> LambdaDslObject
    fn or(name: String, value: Object, rules: MatchingRule...) -> LambdaDslObject
    fn array(name: String, array: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn object(name: String, nestedObject: Consumer<LambdaDslObject>) -> LambdaDslObject
    fn eachLike(name: String, nestedObject: Consumer<LambdaDslObject>) -> LambdaDslObject
    fn eachLike(name: String, numberExamples: Int, nestedObject: Consumer<LambdaDslObject>) -> LambdaDslObject
    fn eachLike(name: String, value: PactDslJsonRootValue) -> LambdaDslObject
    fn eachLike(name: String, value: PactDslJsonRootValue, numberExamples: Int) -> LambdaDslObject
    fn minArrayLike(name: String, size: Integer, nestedObject: Consumer<LambdaDslObject>) -> LambdaDslObject
    fn minArrayLike(name: String, size: Integer, numberExamples: Int, nestedObject: Consumer<LambdaDslObject>) -> LambdaDslObject
    fn minArrayLike(name: String, size: Integer, value: PactDslJsonRootValue, numberExamples: Int) -> LambdaDslObject
    fn maxArrayLike(name: String, size: Integer, nestedObject: Consumer<LambdaDslObject>) -> LambdaDslObject
    fn maxArrayLike(name: String, size: Integer, numberExamples: Int, nestedObject: Consumer<LambdaDslObject>) -> LambdaDslObject
    fn maxArrayLike(name: String, size: Integer, value: PactDslJsonRootValue, numberExamples: Int) -> LambdaDslObject
    fn minMaxArrayLike(name: String, minSize: Integer, maxSize: Integer, nestedObject: Consumer<LambdaDslObject>) -> LambdaDslObject
    fn minMaxArrayLike(name: String, minSize: Integer, maxSize: Integer, numberExamples: Int, nestedObject: Consumer<LambdaDslObject>) -> LambdaDslObject
    fn minMaxArrayLike(name: String, minSize: Integer, maxSize: Integer, value: PactDslJsonRootValue, numberExamples: Int) -> LambdaDslObject
    fn nullValue(fieldName: String) -> LambdaDslObject
    fn eachArrayLike(name: String, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn eachArrayLike(name: String, numberExamples: Int, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn eachArrayWithMaxLike(name: String, size: Integer, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn eachArrayWithMaxLike(name: String, numberExamples: Int, size: Integer, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn eachArrayWithMinLike(name: String, size: Integer, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn eachArrayWithMinLike(name: String, numberExamples: Int, size: Integer, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn eachArrayWithMinMaxLike(name: String, minSize: Integer, maxSize: Integer, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn eachArrayWithMinMaxLike(name: String, minSize: Integer, maxSize: Integer, numberExamples: Int, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn eachKeyMappedToAnArrayLike(exampleKey: String, nestedObject: Consumer<LambdaDslObject>) -> LambdaDslObject
    fn eachKeyLike(exampleKey: String, nestedObject: Consumer<LambdaDslObject>) -> LambdaDslObject
    fn eachKeyLike(exampleKey: String, value: PactDslJsonRootValue) -> LambdaDslObject
    fn dateExpression(name: String, expression: String) -> LambdaDslObject
    fn dateExpression(name: String, expression: String, format: String) -> LambdaDslObject
    fn timeExpression(name: String, expression: String) -> LambdaDslObject
    fn timeExpression(name: String, expression: String, format: String) -> LambdaDslObject
    fn datetimeExpression(name: String, expression: String) -> LambdaDslObject
    fn datetimeExpression(name: String, expression: String, format: String) -> LambdaDslObject
    fn unorderedArray(name: String, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn unorderedMinArray(name: String, size: Int, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn unorderedMaxArray(name: String, size: Int, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn unorderedMinMaxArray(name: String, minSize: Int, maxSize: Int, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
    fn matchUrl(name: String, basePath: String, pathFragments: Object...) -> LambdaDslObject
    fn matchUrl2(name: String, pathFragments: Object...) -> LambdaDslObject
    fn arrayContaining(name: String, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslObject
class LambdaDslJsonArray:
    fn getPactDslJsonArray() -> PactDslJsonArray
    fn object(o: Consumer<LambdaDslObject>) -> LambdaDslJsonArray
    fn array(a: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn unorderedArray(a: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn unorderedMinArray(size: int, a: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn unorderedMaxArray(size: int, a: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn unorderedMinMaxArray(minSize: int, maxSize: int, a: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn stringValue(value: String) -> LambdaDslJsonArray
    fn stringType(example: String) -> LambdaDslJsonArray
    fn stringMatcher(regex: String, example: String) -> LambdaDslJsonArray
    fn numberValue(value: Number) -> LambdaDslJsonArray
    fn numberType(example: Number) -> LambdaDslJsonArray
    fn integerType() -> LambdaDslJsonArray
    fn integerType(example: Long) -> LambdaDslJsonArray
    fn decimalType() -> LambdaDslJsonArray
    fn decimalType(example: BigDecimal) -> LambdaDslJsonArray
    fn decimalType(example: Double) -> LambdaDslJsonArray
    fn numberMatching(regex: String, example: Number) -> LambdaDslJsonArray
    fn decimalMatching(regex: String, example: Double) -> LambdaDslJsonArray
    fn integerMatching(regex: String, example: Integer) -> LambdaDslJsonArray
    fn booleanValue(value: Boolean) -> LambdaDslJsonArray
    fn booleanType(example: Boolean) -> LambdaDslJsonArray
    fn date() -> LambdaDslJsonArray
    fn date(format: String) -> LambdaDslJsonArray
    fn date(format: String, example: Date) -> LambdaDslJsonArray
    fn time() -> LambdaDslJsonArray
    fn time(format: String) -> LambdaDslJsonArray
    fn time(format: String, example: Date) -> LambdaDslJsonArray
    fn id() -> LambdaDslJsonArray
    fn id(example: Long) -> LambdaDslJsonArray
    fn uuid() -> LambdaDslJsonArray
    fn uuid(example: String) -> LambdaDslJsonArray
    fn hexValue() -> LambdaDslJsonArray
    fn hexValue(example: String) -> LambdaDslJsonArray
    fn ipV4Address() -> LambdaDslJsonArray
    fn and(value: Object, rules: MatchingRule...) -> LambdaDslJsonArray
    fn or(value: Object, rules: MatchingRule...) -> LambdaDslJsonArray
    fn eachLike(nestedObject: Consumer<LambdaDslJsonBody>) -> LambdaDslJsonArray
    fn eachLike(value: PactDslJsonRootValue) -> LambdaDslJsonArray
    fn eachLike(value: PactDslJsonRootValue, numberExamples: int) -> LambdaDslJsonArray
    fn eachLike(numberExamples: int, nestedObject: Consumer<LambdaDslJsonBody>) -> LambdaDslJsonArray
    fn minArrayLike(size: Integer, nestedObject: Consumer<LambdaDslJsonBody>) -> LambdaDslJsonArray
    fn minArrayLike(size: Integer, numberExamples: int, nestedObject: Consumer<LambdaDslJsonBody>) -> LambdaDslJsonArray
    fn maxArrayLike(size: Integer, nestedObject: Consumer<LambdaDslJsonBody>) -> LambdaDslJsonArray
    fn maxArrayLike(size: Integer, numberExamples: int, nestedObject: Consumer<LambdaDslJsonBody>) -> LambdaDslJsonArray
    fn minMaxArrayLike(minSize: Integer, maxSize: Integer, nestedObject: Consumer<LambdaDslJsonBody>) -> LambdaDslJsonArray
    fn minMaxArrayLike(minSize: Integer, maxSize: Integer, numberExamples: int, nestedObject: Consumer<LambdaDslJsonBody>) -> LambdaDslJsonArray
    fn nullValue() -> LambdaDslJsonArray
    fn eachArrayLike(nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn eachArrayLike(numberExamples: int, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn eachArrayWithMaxLike(size: Integer, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn eachArrayWithMaxLike(numberExamples: int, size: Integer, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn eachArrayWithMinLike(size: Integer, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn eachArrayWithMinLike(numberExamples: int, size: Integer, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn eachArrayWithMinMaxLike(minSize: Integer, maxSize: Integer, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn eachArrayWithMinMaxLike(minSize: Integer, maxSize: Integer, numberExamples: int, nestedArray: Consumer<LambdaDslJsonArray>) -> LambdaDslJsonArray
    fn dateExpression(expression: String) -> LambdaDslJsonArray
    fn dateExpression(expression: String, format: String) -> LambdaDslJsonArray
    fn timeExpression(expression: String) -> LambdaDslJsonArray
    fn timeExpression(expression: String, format: String) -> LambdaDslJsonArray
    fn datetimeExpression(expression: String) -> LambdaDslJsonArray
    fn datetimeExpression(expression: String, format: String) -> LambdaDslJsonArray
    fn build() -> DslPart
class QuoteUtil:
    fn convert(text: String) -> String
abstract class DslPart:
    fn putObjectPrivate(obj: DslPart) -> Unit
    fn putArrayPrivate(obj: DslPart) -> Unit
    fn array(name: String) -> PactDslJsonArray
    fn array() -> PactDslJsonArray
    fn unorderedArray(name: String) -> PactDslJsonArray
    fn unorderedArray() -> PactDslJsonArray
    fn unorderedMinArray(name: String, size: Int) -> PactDslJsonArray
    fn unorderedMinArray(size: Int) -> PactDslJsonArray
    fn unorderedMaxArray(name: String, size: Int) -> PactDslJsonArray
    fn unorderedMaxArray(size: Int) -> PactDslJsonArray
    fn unorderedMinMaxArray(name: String, minSize: Int, maxSize: Int) -> PactDslJsonArray
    fn unorderedMinMaxArray(minSize: Int, maxSize: Int) -> PactDslJsonArray
    fn closeArray() -> DslPart?
    fn eachLike(name: String) -> PactDslJsonBody
    fn eachLike(name: String, obj: DslPart) -> PactDslJsonBody
    fn eachLike() -> PactDslJsonBody
    fn eachLike(obj: DslPart) -> PactDslJsonArray
    fn eachLike(name: String, numberExamples: Int) -> PactDslJsonBody
    fn eachLike(numberExamples: Int) -> PactDslJsonBody
    fn minArrayLike(name: String, size: Int) -> PactDslJsonBody
    fn minArrayLike(size: Int) -> PactDslJsonBody
    fn minArrayLike(name: String, size: Int, obj: DslPart) -> PactDslJsonBody
    fn minArrayLike(size: Int, obj: DslPart) -> PactDslJsonArray
    fn minArrayLike(name: String, size: Int, numberExamples: Int) -> PactDslJsonBody
    fn minArrayLike(size: Int, numberExamples: Int) -> PactDslJsonBody
    fn maxArrayLike(name: String, size: Int) -> PactDslJsonBody
    fn maxArrayLike(size: Int) -> PactDsl
```

You want to encourage your organisation to use the more modern `LambdaDsl` classes and methods when writing Pact tests. So instead of:

```java
PactDslJsonBody requestBody = new PactDslJsonBody()
    .stringValue("title", "Pact is awesome!")
    .numberType("userId", 42);
```

use:

```java
PactDslJsonBody requestBody = newJsonBody((o) -> {
            o.stringType("title", "Pact is awesome!");
            o.numberType("userId", 42);
        }).build();
```
