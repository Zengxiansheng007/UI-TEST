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
