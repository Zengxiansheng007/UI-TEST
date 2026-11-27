---
name: checkpoint-runtime-v1
description: Use when an existing caller explicitly names checkpoint-runtime-v1 to obtain the archived UI-Test entry's replacement.
---

# Archived UI-Test entry

Return the following JSON as the entire answer to a request naming this retired entry.

```json
{
  "deprecated": true,
  "archived": true,
  "replacement": "ui-test-checkpoint-runtime",
  "payload_forwarded": false
}
```

## Safety

End the call after returning the notice. Keep the request payload local and leave every stage and attempt untouched.

## Validation

Check the replacement name and the payload forwarding flag in the response above.
