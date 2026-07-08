# YAML Reference

Full field-by-field reference for the agenttest suite format.

## Top level

| Field | Type | Required | Description |
|---|---|---|---|
| `version` | string | yes | Must be `"1.0"`. |
| `suite` | string | yes | Suite display name. Used as the key for history/flakiness lookups. |
| `system_prompt` | string | no | System prompt sent to the model. Defaults to empty. |
| `model` | string | yes | Model identifier. Determines which adapter is used (see below). |
| `tools` | list of [Tool](#tool) | no | Tool/function schemas exposed to the model. |
| `tests` | list of [Test](#test) | yes | At least one test is required. |

### Model → adapter dispatch

`get_adapter()` picks an adapter by substring match on the model name (case-insensitive):

| Model contains | Adapter | Requires |
|---|---|---|
| `llama`, `mixtral`, `gemma` | Groq | `GROQ_API_KEY` |
| `claude` | Anthropic | `ANTHROPIC_API_KEY` |
| `gpt` | OpenAI | `OPENAI_API_KEY` |
| anything else | Ollama (local) | a running `ollama serve` |

## Tool

```yaml
tools:
  - name: search_flights
    description: "Search available flights"
    parameters:
      destination: {type: string, description: "City name"}
      date: {type: string, description: "YYYY-MM-DD format"}
    required: [destination, date]
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Function name the model can call. |
| `description` | string | no | Sent to the model to explain the tool. |
| `parameters` | map of name → `{type, description}` | no | Argument schema. `type` is one of `string`, `number`, `boolean`, `object`, `array`. |
| `required` | list of string | no | Which parameter names are required. |

Every function name referenced in a test's `assert_calls` must be declared in `tools` (or `tools` must be empty, which skips validation).

## Test

A test is either **single-turn** (`message`) or **multi-turn** (`conversation`) — never both.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Test display name. |
| `message` | string | single-turn only | The user message sent to the agent. |
| `conversation` | list of [Turn](#turn) | multi-turn only | Sequential turns, each with its own assertions. |
| `runs` | int | no (default `10`) | How many times to repeat this test. |
| `pass_threshold` | float 0–1 | no (default `0.8`) | Minimum pass rate to be considered passing. |
| `assert_calls` | list of [Call assertion](#call-assertion) | no | Tool calls that must have happened. |
| `assert_no_calls` | list of string | no | Function names that must **not** have been called. |
| `assert_order` | list of string | no | Function names that must appear in this relative order (other calls may interleave). |

### Turn

```yaml
conversation:
  - role: user
    message: "Book me a flight to Tokyo"
    assert_calls: [search_flights, book_flight]
  - role: user
    message: "Actually cancel that"
    assert_calls: [cancel_booking]
```

| Field | Type | Required | Description |
|---|---|---|---|
| `role` | string | no (default `user`) | Message role. |
| `message` | string | yes | Message text for this turn. |
| `assert_calls` | list of string | no | Function names expected to be called *during this turn* (name-only check; for argument-level checks on a specific turn, use a single-turn test instead). |

### Call assertion

```yaml
assert_calls:
  - function: book_flight
    after: search_flights
    args:
      flight_id: {type: string, not_null: true}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `function` | string | yes | The function that must have been called. Passes if *any* matching call satisfies all `args` checks. |
| `after` | string | no | The named function must have occurred earlier in the call sequence than this one. |
| `args` | map of arg name → [Arg assertion](#arg-assertion) | no | Per-argument checks. |

### Arg assertion

| Key | Type | Behavior |
|---|---|---|
| `equals` | any | Case-insensitive string match, or numeric equality (`int`/`float` compared as numbers). |
| `type` | `string \| number \| boolean \| object \| array` | Checks the Python type of the actual value. |
| `not_null` | bool | If `true`, the argument must be present and non-null. |
| `contains` | string | Substring match (string arguments only). |
| `matches` | string (regex) | Regex search against a string argument. |

Multiple keys on one arg assertion are combined with AND — all must pass.

## Full example

```yaml
version: "1.0"
suite: "Flight Booking Agent"
system_prompt: "You are a travel booking assistant. Use tools to help users."
model: "llama-3.3-70b-versatile"

tools:
  - name: search_flights
    description: "Search available flights"
    parameters:
      destination: {type: string, description: "City name"}
      date: {type: string, description: "YYYY-MM-DD format"}
      sort_by: {type: string, description: "price or duration"}
    required: [destination, date]
  - name: book_flight
    description: "Book a specific flight"
    parameters:
      flight_id: {type: string}
      passenger_name: {type: string}
    required: [flight_id]

tests:
  - name: "search before booking"
    message: "Book me the cheapest flight to Paris on July 15"
    runs: 20
    pass_threshold: 0.85
    assert_calls:
      - function: search_flights
        args:
          destination: {equals: "Paris"}
          sort_by: {equals: "price"}
      - function: book_flight
        after: search_flights
        args:
          flight_id: {type: string, not_null: true}
    assert_no_calls: [send_confirmation]
    assert_order: [search_flights, book_flight]

  - name: "multi-turn booking and cancel"
    conversation:
      - role: user
        message: "Book me a flight to Tokyo"
        assert_calls: [search_flights, book_flight]
      - role: user
        message: "Actually cancel that"
        assert_calls: [cancel_booking]
    runs: 10
    pass_threshold: 0.80
```
