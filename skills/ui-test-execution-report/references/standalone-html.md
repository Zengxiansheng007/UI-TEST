# Standalone HTML Delivery

The UI image column shows the thumbnail, but the report file itself must contain
the original redacted bitmap bytes. Enlarging reuses those same embedded bytes.
Never shrink, replace or synthesize evidence to reduce the payload. Original
paths and hashes remain metadata, not image loading dependencies.

Use `render_image_evidence` and `install_image_viewer`. PNG, JPEG, GIF and WebP
are accepted as embedded base64 bitmap sources. Missing evidence has an explicit
missing reason and must not be represented as an available screenshot.

Inline CSS and JavaScript; no file URLs, drive paths, relative image/script/style
resources, remote URLs, or CSS resource imports. Optional companion reports must
be labelled separately and are not prerequisites for reading this HTML.

Acceptance checks:

1. Validate `--html-report` and run the image-viewer unit tests.
2. Copy only the HTML into an empty directory, disable networking, and open it.
3. All expected thumbnails decode, and their byte hashes match the evidence.
4. Desktop and mobile support fit-width, fit-window, original-size, zoom and scroll.
5. Closing restores focus and page scroll; no sidecar/network requests or JS errors.

Email or chat attachment previews may disable JavaScript. Verify the delivered
file in a current browser; sharing HTML does not publish evidence externally.
Business results, missing-evidence findings and source hashes stay unchanged.

## 阶段报告截图

阶段报告按输入顺序显示用例和步骤。步骤的 `images` 是有序截图数组。每项提供图片来源、SHA-256、`role`（`key` 或 `ordinary`），可加 `caption`。正式 V5 使用运行目录相对 `path` 且必须包含在该步 `evidence_refs`。适配器核对路径边界，查看器校验原图摘要。步骤可提供 `key_reason` 说明原因。工程师从目录直达用例和关键节点，从各步单独展开普通图，点击图像可按原始尺寸审阅并返回原处。证据索引与可选原始回放入口位于过程区之后。

同一尝试中的截图以对象、观察时点和业务状态归组。同一动作留下多图时，显式传入相同的 `object_ref`、`point`、`state_ref`（默认用 `observation`）；区分同类事件的多次发生时传 `moment_ref`。作者实际核对画面后可用 `preferred` 指定本组代表图。能读出对象与状态的图标 `support="direct"`（默认）；只提供上下文的图标 `support="context"`，保留在索引。只有回执本身满足用例目标且画面足以证明时，才给该图填写 `final_goal`，记录具体目标。后续状态变化另行记录。
