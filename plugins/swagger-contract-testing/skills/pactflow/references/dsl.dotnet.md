While you already know this, here is a reminder of the Pact .NET interfaces, types, classes and methods you will need to use to create a Pact test in C# (having omitted deprecated and unadvised methods):

**File: src/PactNet/IRequestBuilderV2.cs**
```
namespace PactNet
{
    public interface IRequestBuilderV2
    {
        IRequestBuilderV2 Given(string providerState);
        IRequestBuilderV2 WithRequest(HttpMethod method, string path);
        IRequestBuilderV2 WithRequest(string method, string path);
        IRequestBuilderV2 WithQuery(string key, string value);
        IRequestBuilderV2 WithHeader(string key, string value);
        IRequestBuilderV2 WithHeader(string key, IMatcher matcher);
        IRequestBuilderV2 WithJsonBody(dynamic body);
        IRequestBuilderV2 WithJsonBody(dynamic body, string contentType);
        IRequestBuilderV2 WithJsonBody(dynamic body, JsonSerializerOptions settings);
        IRequestBuilderV2 WithJsonBody(dynamic body, JsonSerializerOptions settings, string contentType);
        IRequestBuilderV2 WithBody(string body, string contentType);
        IResponseBuilderV2 WillRespond();
    }
}
```

**File: src/PactNet/IRequestBuilderV3.cs**
```
namespace PactNet
{
    public interface IRequestBuilderV3
    {
        IRequestBuilderV3 Given(string providerState);
        IRequestBuilderV3 Given(string providerState, IDictionary<string, string> parameters);
        IRequestBuilderV3 WithRequest(HttpMethod method, string path);
        IRequestBuilderV3 WithRequest(string method, string path);
        IRequestBuilderV3 WithQuery(string key, string value);
        IRequestBuilderV3 WithQuery(string key, IMatcher matcher);
        IRequestBuilderV3 WithHeader(string key, string value);
        IRequestBuilderV3 WithHeader(string key, IMatcher matcher);
        IRequestBuilderV3 WithJsonBody(dynamic body);
        IRequestBuilderV3 WithJsonBody(dynamic body, string contentType);
        IRequestBuilderV3 WithJsonBody(dynamic body, JsonSerializerOptions settings);
        IRequestBuilderV3 WithJsonBody(dynamic body, JsonSerializerOptions settings, string contentType);
        IRequestBuilderV3 WithBody(string body, string contentType);
        IResponseBuilderV3 WillRespond();
    }
}
```

**File: src/PactNet/IRequestBuilderV4.cs**
```
namespace PactNet
{
    public interface IRequestBuilderV4
    {
        IRequestBuilderV4 Given(string providerState);
        IRequestBuilderV4 Given(string providerState, IDictionary<string, string> parameters);
        IRequestBuilderV4 WithRequest(HttpMethod method, string path);
        IRequestBuilderV4 WithRequest(string method, string path);
        IRequestBuilderV4 WithQuery(string key, string value);
        IRequestBuilderV4 WithQuery(string key, IMatcher matcher);
        IRequestBuilderV4 WithHeader(string key, string value);
        IRequestBuilderV4 WithHeader(string key, IMatcher matcher);
        IRequestBuilderV4 WithJsonBody(dynamic body);
        IRequestBuilderV4 WithJsonBody(dynamic body, string contentType);
        IRequestBuilderV4 WithJsonBody(dynamic body, JsonSerializerOptions settings);
        IRequestBuilderV4 WithJsonBody(dynamic body, JsonSerializerOptions settings, string contentType);
        IRequestBuilderV4 WithBody(string body, string contentType);
        IResponseBuilderV4 WillRespond();
    }
}
```

**File: src/PactNet/IResponseBuilderV2.cs**
```
namespace PactNet
{
    public interface IResponseBuilderV2
    {
        IResponseBuilderV2 WithStatus(HttpStatusCode status);
        IResponseBuilderV2 WithHeader(string key, string value);
        IResponseBuilderV2 WithHeader(string key, IMatcher matcher);
        IResponseBuilderV2 WithJsonBody(dynamic body);
        IResponseBuilderV2 WithJsonBody(dynamic body, string contentType);
        IResponseBuilderV2 WithJsonBody(dynamic body, JsonSerializerOptions settings);
        IResponseBuilderV2 WithJsonBody(dynamic body, JsonSerializerOptions settings, string contentType);
        IResponseBuilderV2 WithBody(string body, string contentType);
    }
}
```

**File: src/PactNet/IResponseBuilderV3.cs**
```
namespace PactNet
{
    public interface IResponseBuilderV3
    {
        IResponseBuilderV3 WithStatus(HttpStatusCode status);
        IResponseBuilderV3 WithHeader(string key, string value);
        IResponseBuilderV3 WithHeader(string key, IMatcher matcher);
        IResponseBuilderV3 WithJsonBody(dynamic body);
        IResponseBuilderV3 WithJsonBody(dynamic body, string contentType);
        IResponseBuilderV3 WithJsonBody(dynamic body, JsonSerializerOptions settings);
        IResponseBuilderV3 WithJsonBody(dynamic body, JsonSerializerOptions settings, string contentType);
        IResponseBuilderV3 WithBody(string body, string contentType);
    }
}
```

**File: src/PactNet/IResponseBuilderV4.cs**
```
namespace PactNet
{
    public interface IResponseBuilderV4
    {
        IResponseBuilderV4 WithStatus(HttpStatusCode status);
        IResponseBuilderV4 WithHeader(string key, string value);
        IResponseBuilderV4 WithHeader(string key, IMatcher matcher);
        IResponseBuilderV4 WithJsonBody(dynamic body);
        IResponseBuilderV4 WithJsonBody(dynamic body, string contentType);
        IResponseBuilderV4 WithJsonBody(dynamic body, JsonSerializerOptions settings);
        IResponseBuilderV4 WithJsonBody(dynamic body, JsonSerializerOptions settings, string contentType);
        IResponseBuilderV4 WithBody(string body, string contentType);
    }
}
```

**File: src/PactNet/IConsumerContext.cs**
```
namespace PactNet
{
    public interface IConsumerContext
    {
        Uri MockServerUri { get; }
    }
}
```

**File: src/PactNet/IPactBuilderV2.cs**
```
namespace PactNet
{
    public interface IPactBuilderV2
    {
        IRequestBuilderV2 UponReceiving(string description);
        void Verify(Action<IConsumerContext> interact);
        Task VerifyAsync(Func<IConsumerContext, Task> interact);
    }
}
```

**File: src/PactNet/IPactBuilderV3.cs**
```
namespace PactNet
{
    public interface IPactBuilderV3
    {
        IRequestBuilderV3 UponReceiving(string description);
        void Verify(Action<IConsumerContext> interact);
        Task VerifyAsync(Func<IConsumerContext, Task> interact);
    }
}
```

**File: src/PactNet/IPactBuilderV4.cs**
```
namespace PactNet
{
    public interface IPactBuilderV4
    {
        IRequestBuilderV4 UponReceiving(string description);
        void Verify(Action<IConsumerContext> interact);
        Task VerifyAsync(Func<IConsumerContext, Task> interact);
    }
}
```

**File: src/PactNet/Pact.cs**
```
namespace PactNet
{
    public static class Pact
    {
        public static IPactBuilderV2 V2(string consumer, string provider, PactConfig config);
        public static IPactBuilderV3 V3(string consumer, string provider, PactConfig config);
        public static IPactBuilderV4 V4(string consumer, string provider, PactConfig config);
    }
}
```

**File: src/PactNet/PactConfig.cs**
```
namespace PactNet
{
    public class PactConfig
    {
        public string PactDir { get; set; }
        public string LogDir { get; set; }
        public JsonSerializerOptions DefaultJsonSettings { get; set; }
        public Action<string> Outputters { get; set; }
    }
}
```

File: src/PactNet.Abstractions/Matchers/Match.cs
```
namespace PactNet.Matchers
{
    public static class Match
    {
        public static IMatcher Regex(string example, string pattern);
        public static IMatcher Type(object example);
        public static IMatcher MinType(object example, int min);
        public static IMatcher MaxType(object example, int max);
        public static IMatcher Decimal(decimal example);
        public static IMatcher Number(int example);
        public static IMatcher Number(double example);
        public static IMatcher Number(float example);
        public static IMatcher Number(decimal example);
        public static IMatcher Equality(dynamic example);
        public static IMatcher Null();
        public static IMatcher Include(string example);
    }
}
```

File: src/PactNet.Abstractions/PactConfig.cs
```
namespace PactNet
{
    public class PactConfig
    {
        public string PactDir { get; set; }
        public string LogDir { get; set; }
        public JsonSerializerOptions DefaultJsonSettings { get; set; }
        public Action<string> Outputters { get; set; }
    }
}
```

File: src/PactNet.Abstractions/Infrastructure/Outputters/IOutput.cs
```
namespace PactNet.Infrastructure.Outputters
{
    public interface IOutput
    {
        void WriteLine(string line);
    }
}
```

Make sure to use `Pact.V4` interface from the latest version (5.x.x) of the Pact .NET library, as this is the most up-to-date version.
