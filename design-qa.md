# Design QA

## Comparison setup

- Source visual truth: `artifacts/figma-reference.png`
- Source Figma node: `https://www.figma.com/design/5gUwaaByGkmrdu3w1v5d5i?node-id=3-9`
- Implementation screenshot: `artifacts/implementation.png`
- Full comparison: `artifacts/design-comparison.png`
- Focused chart/control comparison: `artifacts/focused-chart-control.png`
- Focused table comparison: `artifacts/focused-samples-table.png`
- Viewport: 1440 × 1024 desktop dashboard
- Source pixels: 1440 × 1024
- Implementation pixels: 1440 × 1024
- CSS/device density normalization: not applicable; both artifacts are 1× desktop pixels
- State: simulator mode selected, collection running, 500 ms interval, 2.5 V threshold, four recent sample rows

## Full-view comparison evidence

The combined comparison places the Figma reference on the left and the PySide6 render on the right. Both use the same crop and pixel dimensions. The header height, 48 px page margins, overview block, four-card grid, chart/control split, 24 px section rhythm, and 232 px sampling panel align without clipping or overflow.

## Focused comparison evidence

The chart/control crop confirms the 916/408 region proportions, plot bounds, warning line, legends, notice panel, and button states. The control-card contents intentionally extend the design with data-mode, COM-port, refresh and baud-rate controls requested after the original Figma pass. The plotted values are runtime data, so exact polyline vertices are intentionally data-dependent; chart geometry and visual treatment match the source.

The sampling-table crop confirms the left-aligned column labels, 360/360/576 column proportions, four 32 px rows, semantic warning color, and CSV status pill.

## Required fidelity surfaces

- Fonts and typography: passed. The project bundles and loads Noto Sans SC, with the source hierarchy reproduced for product title, section titles, metrics, captions, table text, and control labels. No wrapping or truncation was observed at 1440 × 1024.
- Spacing and layout rhythm: passed. Header, content margins, section gaps, card heights, panel split, radii, borders, shadows, and table density match the source at the target viewport.
- Colors and visual tokens: passed. Neutral surfaces, dark brand color, secondary gray, positive green, danger red, disabled controls, and warning background follow the Figma tokens.
- Image quality and asset fidelity: passed. The voltage-wave and status-dot assets are the exact exported Figma SVGs. The chart is a native data visualization rather than a raster placeholder.
- Copy and content: passed. Product, device, sampling, threshold, button, table, and CSV strings retain the design language. The mode/port copy is an intentional functional extension aligned with the later GPT Work requirements.
- Interaction and accessibility: passed for the scoped desktop flow. Start/stop button state, timer state, warning state, table update, keyboard focus border, and semantic color changes were tested. The page remains reachable in smaller windows through the scroll area.

## Comparison history

### Iteration 1

- [P2] The first table render centered the header labels, while Figma left-aligns them.
  - Fix: set explicit left/vertical-center alignment on every horizontal-header item.
- [P2] The snapshot chart's final point displayed 2.14 V while the current metric and Figma label displayed 2.36 V.
  - Fix: align the final snapshot point to 2.36 V.

### Iteration 2

Post-fix evidence is recorded in `artifacts/design-comparison.png`, `artifacts/focused-chart-control.png`, and `artifacts/focused-samples-table.png`. No actionable P0, P1, or P2 visual differences remain.

### Iteration 3 — dual data-source extension

- Replaced the static “模拟数据” chip with a simulator/serial mode selector.
- Added port selection, refresh, baud-rate and inline connection/error states inside the existing control-card footprint.
- Preserved the original frame, spacing, card proportions, typography and semantic colors.
- Added `artifacts/serial-mode-no-port.png` to verify the no-COM error state.

## Functional verification

- Python compilation: passed for all project Python files.
- Offscreen application creation at 1440 × 1024: passed.
- Start → stop → start control flow and timer/button synchronization: passed.
- Injected 2.80 V warning flow, warning status, table status, and recorder call: passed.
- Simulator source, fake serial read/close, and missing-port error unit tests: 3 passed.
- Simulator → no-COM serial → simulator switching without an application crash: passed.
- Bundled Noto Sans SC registration: passed.
- Browser console check: not applicable to this native PySide6 desktop application; the offscreen Qt render completed without runtime exceptions.

## Findings

No actionable P0, P1, or P2 findings remain. Differences in the header source chip and control-card rows are authorized functionality, not visual regressions.

## Follow-up polish

- [P3] Validate the serial state with a physical USB-to-TTL adapter and real STM32 USART1 output when the hardware is available.

## Implementation checklist

- [x] Match target desktop structure and spacing.
- [x] Bundle source-accurate font and vector assets.
- [x] Preserve live data, warning, plotting, controls, and CSV behavior.
- [x] Verify visual state at the source viewport.
- [x] Verify primary interactions and warning behavior.

final result: passed
