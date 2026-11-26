# Evidence Taxonomy

Evidence layers:

- `ui`: route, selected state, visible text, form value, screenshot, console error.
- `api`: redacted result from a matched current-session page response.
- `contract`: schema, required field, enum, type, backward compatibility.
- `task`: status observed in the page, including a terminal state when visible.
- `downstream`: sync result or list/detail consistency observed through the authorized UI flow.
- `ai-vision`: prompt, model, response, latency, retry, confidence if available.
- `environment`: network, auth, account, data, browser, VPN, proxy.

For example, when a tester clicks **Check status**, the page loads its own status response. Record the matched response reference from that run and session. If the response is missing and the case accepts the visible **Available** result, record that UI assertion and its source. If neither establishes the required state, mark the evidence missing and retain any failure already observed.
