# Sample exports

Small, valid files for the artifact-export tests (`artifact register`).

| File | Used for |
|---|---|
| `wireframe.png`, `wireframe.svg`, `wireframe.pdf`, `wireframe.jpg` | the four allowed formats |
| `wireframe.gif` | `artifact-format-not-allowed` (a format outside png, svg, pdf, jpg, jpeg) |
| `wireframe-changed.png` | a copy of `wireframe.png` with one byte flipped, for `artifact-hash-mismatch` |

Regenerate nothing by hand: the tests hash these files, so any edit changes their expectations.
