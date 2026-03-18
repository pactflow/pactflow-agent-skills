# Drift Lua API — Full Reference

## Contents

- [Script Structure](#script-structure)
- [Built-in Functions](#built-in-functions)
- [Standard Lua Modules](#standard-lua-modules)
- [Lifecycle Events](#lifecycle-events)
- [Common Patterns](#common-patterns)
- [Embedding in Test Frameworks](#embedding-in-test-frameworks)

---

Drift embeds Lua 5.4. Scripts are loaded as sources and used for lifecycle hooks and exported
functions callable from YAML expressions.

---

## Script Structure

Every Drift Lua script must return an exports table:

```lua
local exports = {
  event_handlers = {
    ["operation:started"] = function(event, data)
      -- setup logic
    end,
    -- ... other events
  },
  exported_functions = {
    -- called via ${functions:function_name} in YAML
    my_function = function()
      return "some value"
    end
  }
}

return exports
```

---

## Built-in Functions

### `http(request_table)`

Makes a synchronous HTTP request. Tables in `body` are auto-serialized to JSON.

```lua
local res = http({
  url    = "http://localhost:8080/products",   -- required
  method = "POST",                             -- default: GET
  query  = { page = 1, limit = 10 },          -- string or table
  headers = {
    ["content-type"] = "application/json",
    authorization = "Bearer " .. token
  },
  body = {                                     -- table auto-JSON-encoded
    id = 10,
    name = "Test Product",
    price = 9.99
  }
})

-- Response fields:
res.status   -- integer HTTP status code
res.headers  -- table of response headers
res.body     -- string or table (JSON auto-parsed into table)
```

### `dbg(data)`

Pretty-prints a Lua table as a human-readable string — useful for inspecting event data.

```lua
["operation:started"] = function(event, data)
  print(dbg(data))   -- prints the full data structure
end
```

---

## Standard Lua Modules

- `os` — environment variables (`os.getenv("VAR")`), time (`os.time()`)
- `io` — file system operations
- `math` — math functions (`math.random()`)
- `string` — string manipulation
- `table` — table utilities

Pure-Lua LuaRocks packages are supported (no C/FFI extensions):

```bash
luarocks install dkjson
```

```lua
local json = require("dkjson")
print(json.encode({ status = "ok" }))
```

Set LuaRocks paths:

```bash
export LUA_PATH="$HOME/.luarocks/share/lua/5.4/?.lua;;"
export LUA_CPATH="$HOME/.luarocks/lib/lua/5.4/?.so;;"
```

---

## Lifecycle Events

### Event Reference

| Event                | Fires                                  | Notes                         |
| -------------------- | -------------------------------------- | ----------------------------- |
| `testcase:started`   | Once, before all operations            | Suite-level setup             |
| `testcase:finished`  | Once, after all operations             | Suite-level teardown          |
| `operation:started`  | Before each operation                  | Create precondition data      |
| `operation:prepared` | After parameters resolved, before HTTP | Last chance to modify params  |
| `operation:finished` | After each operation completes         | Per-test cleanup              |
| `operation:failed`   | When an operation fails                | Diagnostics, error handling   |
| `http:request`       | Before every outgoing HTTP call        | **Must return modified data** |

### `http:request` — must return data

```lua
["http:request"] = function(event, data)
  data.headers["x-timestamp"] = tostring(os.time())
  data.headers["x-signature"] = compute_signature(data.body)
  return data   -- REQUIRED — must return modified data
end
```

---

## Common Patterns

### State setup and teardown

```lua
local exports = {
  event_handlers = {
    ["operation:started"] = function(event, data)
      -- data.operation contains the operation name/ID
      http({
        url = "http://localhost:8080/products",
        method = "POST",
        body = { id = 10, name = "Test Product", price = 9.99 }
      })
    end,

    ["operation:finished"] = function(event, data)
      http({
        url = "http://localhost:8080/products/10",
        method = "DELETE"
      })
    end
  }
}
return exports
```

### State setup by operation name

```lua
local setup_handlers = {
  ["deleteProduct_Success"] = function()
    http({ url = "http://localhost:8080/products", method = "POST",
           body = { id = 10, name = "Test" } })
  end,
  ["updateProduct_Success"] = function()
    http({ url = "http://localhost:8080/products", method = "POST",
           body = { id = 10, name = "Original" } })
  end
}

local exports = {
  event_handlers = {
    ["operation:started"] = function(event, data)
      local handler = setup_handlers[data.operation]
      if handler then handler() end
    end,

    ["operation:finished"] = function(event, data)
      http({ url = "http://localhost:8080/test/reset", method = "POST" })
    end
  }
}
return exports
```

### Dynamic auth token

```lua
local cached_token = nil

local function get_token()
  if cached_token then return cached_token end
  local res = http({
    url = "http://localhost:8080/auth/token",
    method = "POST",
    body = { username = "test", password = os.getenv("TEST_PASSWORD") }
  })
  cached_token = res.body.token
  return cached_token
end

local exports = {
  exported_functions = {
    bearer_token = get_token,
    readonly_token = function()
      -- return a different token with limited scope
      return os.getenv("READONLY_TOKEN")
    end
  }
}
return exports
```

YAML usage:

```yaml
global:
  auth:
    parameters:
      authentication:
        scheme: bearer
        token: ${functions:bearer_token}
```

### Dynamic request IDs and UUIDs

```lua
local exports = {
  exported_functions = {
    generate_request_id = function()
      return string.format("req-%d-%d", os.time(), math.random(1000, 9999))
    end
  }
}
return exports
```

YAML usage:

```yaml
parameters:
  headers:
    x-request-id: ${functions:generate_request_id}
```

### Suite-level setup (run once)

```lua
local exports = {
  event_handlers = {
    ["testcase:started"] = function(event, data)
      -- Seed the database once before all tests
      http({ url = "http://localhost:8080/test/seed", method = "POST" })
    end,

    ["testcase:finished"] = function(event, data)
      -- Wipe test data after all tests complete
      http({ url = "http://localhost:8080/test/reset", method = "POST" })
    end
  }
}
return exports
```

### Debugging event data

```lua
local exports = {
  event_handlers = {
    ["operation:started"] = function(event, data)
      print("Event: " .. event)
      print(dbg(data))
    end
  }
}
return exports
```

---

## Embedding in Test Frameworks

Drift runs as a subprocess. Wrap it in your existing test runner:

### Jest (Node.js)

```javascript
const { spawn } = require("child_process");

const runDrift = (options = {}) => {
  const { testFile = "./drift.yaml", serverUrl = "http://localhost:8080" } =
    options;
  return new Promise((resolve, reject) => {
    const child = spawn(
      "drift",
      ["verify", "--test-files", testFile, "--server-url", serverUrl],
      { stdio: "inherit", shell: true },
    );
    child.on("close", (code) => resolve(code ?? 1));
    child.on("error", reject);
  });
};

// In your test:
it("conforms to OpenAPI spec", async () => {
  const exitCode = await runDrift();
  expect(exitCode).toBe(0);
});
```

### pytest (Python)

```python
import subprocess

def run_drift(test_file='./drift.yaml', server_url='http://localhost:8080'):
    result = subprocess.run([
        'drift', 'verify', '--test-files', test_file, '--server-url', server_url
    ])
    return result.returncode

def test_api_conforms_to_spec(api_server):
    assert run_drift() == 0, "Drift contract tests failed"
```
