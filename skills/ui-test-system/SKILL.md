---
name: ui-test-system
description: Use when an existing caller explicitly names ui-test-system to obtain the archived UI-Test entry's replacement.
---

# Archived UI-Test entry

Return the following JSON as the entire answer to a request naming this retired entry.

```json
{
  "deprecated": true,
  "replacement": "ui-test",
  "route": "ui-test",
  "payloadForwarded": false,
  "statusCode": "archived",
  "statusLabelZh": "已归档"
}
```

## Safety

End the call after returning the notice. Keep the request payload local and leave every stage and attempt untouched.

## Validation

Check the replacement name and the payload forwarding flag in the response above.
