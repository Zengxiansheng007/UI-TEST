# CR-20261118-006 — ModuleReadyContext 2.0



| Field | Value |

| --- | --- |

| Change ID | CR-20261118-006 |

| Status | applied |



## Summary



Current-session browser readiness under issue #6, AC-004 and the readiness portions of AC-008/009.



## Context And Problem



The checkpoint and primary producers used distinct version-1 layouts. A ready flag and an opaque response reference could bypass evidence checks.



## Sections Changed



Module observation, context validation, checkpoint live module entry, exploration and Midscene preflight share the primary contract. The main skill registers the new schema and deprecates version 1.



## Decision And Alternatives



Observe the existing page's response events before the authorized UI operation. Count distinct visible DOM elements. Match HTTP business success and retain only redacted evidence.



## Impact Analysis



New consumers require current task, page and session inputs. Existing button recovery remains on its separate execution path.



## Validation Evidence



Latest-request rejection was reproduced in visible Edge before repair. The visible Edge loopback regression covers the public checkpoint CLI, shared capture and consumption, and a simulated Midscene callback. Independent candidate and command receipts are under .scratch/t05/runtime-3/.



## Safety And Privacy



Only the controlled local page generated test traffic. No external model or real business action was invoked. The observer retains no response body, request headers or credential values in the context.



## Risks And Follow-up



The caller supplies the login marker and response assertion for the module. Wider network behavior is covered by T08.

