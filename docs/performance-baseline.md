# Application performance baseline and proposed optimization plan

## Status

Analysis and baseline measurements only. Application algorithms have not been
changed. Optimization implementation awaits approval.

Branch: `perf/application-baseline`; starting commit: `13c942c`.

## Licenses and inspiration

Read `../siril-master/LICENSE.md` (GPLv3) and this project's `LICENSE` (GPLv3).
GPLv3 allows running, modifying, sharing and selling the program. Distribution
must preserve license/copyright notices, identify modifications and provide
Corresponding Source under GPLv3; binary distribution must offer source through
one of the license's permitted mechanisms. Private modification does not itself
require publication. Ordinary output images are not automatically GPL-covered.

General architectural ideas and algorithms can be implemented independently.
No Siril implementation code was copied or translated. Only its license, README
and top-level module organization were inspected: `gui`, `core`, `io`, `algos`,
`filters`, `registration`, `stacking`. Existing source comments in Astro naming
Siril/GraXpert predate this performance work and are not a new provenance audit.

Added dependencies: **none**. Measurements use Python's `cProfile`, `pstats`,
`perf_counter` and already-installed NumPy/OpenCV/PyQt5/ONNX Runtime/Astropy.
No new library installation is proposed for the first implementation stages.

## Environment and methodology

- Linux 7.0.0-38-generic, x86_64, glibc 2.43.
- Intel i7-3610QM, 4 physical cores / 8 threads; approximately 12 GiB RAM.
- Python 3.14.4; NumPy 2.5.3; OpenCV 5.0.0 (8 threads); PyQt5 5.15.11.
- These NumPy/OpenCV versions differ from `requirements.txt` pins.
- Synthetic reproducible 6000 x 4000 x 3 `float32` BGR image: 288 MB
  (274.7 MiB), background gradient plus random noise, seed 20261018.
- Curves: `(48,64), (128,168), (210,235)`, linear mode, RGB selected.
- Preview: 1200 x 800; neutral basic/HSL/Levels settings unless stated.
- 3 timing repetitions; 5 for GUI/curve scenarios; 2 for selected AI/heavy
  scenarios. Medians below are unprofiled wall time. An additional call produces
  a cProfile file for bottleneck attribution.
- Actual application methods, Levels/Curves dialogs and BlendViewer run with
  an offscreen QApplication. The host omits unrelated toolbar construction,
  thumbnails, panel and overlay updates. GUI results are lower-bound benchmarks,
  not a physical-screen latency certification or a complete application startup
  benchmark. The curve measurement starts at `_on_curves_changed` and ends at
  synchronous viewport repaint, including its 45 ms timer.
- Full async refresh timer is not connected in the benchmark host. Contention
  between preview and full workers requires a subsequent integrated test.
- FITS reads are warm OS-cache reads; writes measure encode/write return, not
  durable-storage `fsync`. Loading measures the entire load callback, including
  its initial processing, rather than the earliest visible intermediate frame.
- Stack scenarios use three references to the same input to isolate integration
  cost, not alignment or realistic heterogeneous-frame rejection.

Measurement script: `/tmp/opencode/profile_astro_baseline.py`.
Raw samples and cProfile summaries: `/tmp/opencode/baseline_results.json`.
Per-scenario profiles: `/tmp/opencode/<scenario>.prof`.
Temporary artifacts are outside the application repository.

## Structure and data flow

`Astro Ai Processor.py` combines most GUI dialogs, `AstroApp` document state,
viewer/history/layers, image I/O, command console, model orchestration, ONNX tile
processing, stacking/mosaic/video workers and external-tool subprocesses.

Numerical modules:

- `processing/color_processor.py`: Camera Raw, calibration, HSL, star correction,
  GHS and classic denoise.
- `processing/tonal_adjustments.py`: Levels, curve LUT generation/application.
- `processing/stretch.py`: linear, AutoStretch and histogram screen transforms.
- `processing/background_extraction.py`: sampling, interpolation, AI background
  maps and correction.
- `processing/image_effects.py`: background neutralization and local contrast.
- `processing/image_analysis.py`: lazy astronomy backends, noise and star metrics.
- `processing/stacking.py`: frame normalization and chunked integration.
- `processing/astro_upscale.py`: interpolation, anti-ringing, masks and metadata.
- `deep_sky_catalog.py`: object metadata; `update_api_server.py`: update
  infrastructure outside the image hot path.

Flow:

1. `safe_imread`/`safe_fits_read_with_header` decode pixels.
2. `normalize_to_linear_bgr` normalizes layout/range. Loading creates native,
   original, working (`magic_img`) and processed arrays.
3. `get_effective_magic_img` assembles visible image layers/masks.
4. Camera Raw/HSL/GHS -> Levels -> Curves -> optional persistent AutoStretch.
5. Full output becomes `processed_img`; preview instead downsamples assembled
   source and processes it independently.
6. Optional display stretch -> channel visibility -> uint8/QImage/QPixmap ->
   BlendViewer/SingleViewer. Display stretching does not change export pixels.
7. Image/FITS export writes `processed_img`; deepSNR exports uint16 BGR TIFF.

The processing pipeline is repeated in synchronous, asynchronous-worker and
preview methods. Curves start a 45 ms timer; `on_params_changed` executes preview
synchronously and schedules full asynchronous processing after 200 ms.

## Baseline results

| Scenario | Median |
| --- | ---: |
| Curve change -> viewport repaint | 284.4 ms |
| Curve change with Before/After compare | 298.4 ms |
| Preview processing alone | 253.7 ms |
| Preview with display AutoStretch | 404.6 ms |
| Full effective-image copy | 77.5 ms |
| Downsample full image to 1200 px | 32.9 ms |
| Build curve LUT | 0.30 ms |
| Apply curves to full float image | 832.1 ms |
| Neutral Levels, full image | 1178.9 ms |
| Neutral Camera Raw/HSL, full image | 406.3 ms |
| Full pipeline with curve, including viewer update | 2955.6 ms |
| Full float image -> QPixmap | 828.6 ms |
| Full AutoStretch | 2332.0 ms |
| Full histogram stretch | 2676.7 ms |
| FITS decode | 76.1 ms |
| Load callback including processing/viewer | 5167.9 ms |
| FITS export | 2853.2 ms |
| deepSNR float -> uint16 conversion | 992.5 ms |
| uint16 TIFF encode/write | 3053.2 ms |
| Local contrast, radius 12 | 1670.3 ms |
| Gaussian blur, sigma 3 | 194.3 ms |
| HSL on preview, one hue band | 100.5 ms |
| GHS on preview, stretch factor 2 | 141.4 ms |
| Image analysis, full image | 2014.7 ms |
| Average integration, 3 full frames | 1097.5 ms |
| Median integration, 3 full frames | 4735.7 ms |
| Upscale 2x, 1200 x 800 source | 96.2 ms |
| AI background extraction, full image | 2064.0 ms |
| Denoise ONNX session, cold initialization | 4625.7 ms (one sample) |
| Denoise ONNX tile, 256 x 256 | 3459.4 ms (two samples) |

AI measurements use existing local GraXpert models: background `1.0.1`, denoise
`3.0.2`, CPU provider. Denoise measurements cover a real tile, not a full-image
denoise run; no whole-image AI speedup claim is made. A cold session's separate
cProfile call is a cached lookup, so it is not a cold initialization profile.

## Measured bottlenecks

1. **Preview source preparation:** full working-image copying costs ~78 ms before
   downsampling. Together these consume >100 ms before any preview adjustment.
2. **Neutral passes:** neutral Levels still sanitize, calculate and copy every
   selected channel (~1.18 s standalone full-size). Neutral Camera Raw/HSL spends
   almost all its ~406 ms in repeated clipping.
3. **Curves:** LUT construction is negligible. Full source conversion accounts
   for ~663 of ~833 profiled ms; LUT application itself ~98 ms. Current float
   curves return uint8. This is existing behavior and must be preserved by the
   optimization reference tests, not silently replaced with high-precision output.
4. **Rendering:** full float -> QPixmap ~829 ms, mostly float sanitization,
   scaling, clipping and copies. Loading performs this three times and runs the
   full neutral pipeline synchronously.
5. **Stretch:** full MTF application and array passes dominate AutoStretch;
   preview statistics alone consume ~93 ms in the profiled stretch scenario.
6. **Export:** uint16 conversion creates full float64 temporaries. TIFF coding
   spends ~2.93 s inside `imencode`; ~0.11 s in file output. FITS layout/endian
   handling and array writing dominate its ~2.85 s.
7. **AI:** background extraction creates a fresh session each request; profiled
   session construction ~576 ms, inference ~372 ms. Denoise already caches
   sessions; inference accounts for ~3325 of ~3326 profiled ms per tile.
8. **Other heavy work:** sigma clipping/percentiles dominate analysis; median
   partition dominates integration; Gaussian blur plus array arithmetic dominate
   local contrast. These already use native NumPy/OpenCV algorithms.

## Proposed stages (estimates, not achieved results)

Each implemented stage should be a small commit with old/new reference tests,
benchmark samples and a report update. Changes must remain independent of Siril
implementation code.

1. **Reproducible benchmark harness and pipeline snapshot tests.** Keep a frozen
   reference in tests, cover uint8/uint16/float32, NaN/Inf, channels, curves,
   cancellation and export freshness. Use stdlib benchmarks initially; no new
   dependency needed. No speedup expected from instrumentation itself.
2. **Revision-keyed preview source/stage cache.** Cache downsampled composition,
   invalidate for load/undo/redo/layers/masks/geometry edits. A curve drag should
   reuse upstream Camera Raw/HSL/Levels output. Target ~30–60 ms preview compute
   and ~50–90 ms event-to-repaint, versus 284–298 ms today (~3–6x). Use adaptive
   preview resolution for combined expensive effects; zoom should preserve image
   coordinates and refine the viewport/ROI after interaction.
3. **Preview scheduling/rendering.** Coalesce updates while dragging rather than
   postpone indefinitely; a latest-request-wins worker and revision rejection
   prevent stale frames. Create QPixmap only on the GUI thread. Cache Before,
   suppress full-size screen conversion and redundant panel/overlay work. Limit
   contention with full-size background jobs. A thread alone is responsiveness,
   not a guaranteed computation speedup.
4. **Exact full-pipeline fast paths and fewer temporaries.** Consolidate shared
   pipeline code; skip provably neutral work and use safe owned work buffers.
   Preserve dtype, rounding, channel behavior and sanitization. Estimate 1.5–3x
   full neutral/curve pipeline improvement; validate bit-exactly first.
5. **Preview-only GHS/stretch approximations.** Cache sampled statistics and LUTs;
   use reduced resolution and/or interpolation solely for interactive output.
   Estimate 3–8x interactive combined stretch improvement. Full-size export uses
   the unchanged exact transform unless equivalence is separately demonstrated.
6. **I/O and deepSNR export.** Perform decode/export in workers; build the first
   preview before full processing. Chunk precision-preserving uint16 conversion
   (float64 arithmetic where required for exact rounding). Optimize contiguous
   FITS layout; benchmark equivalent lossless TIFF compression options before
   choosing a tradeoff. Estimate 2–5x first-preview improvement and 1.3–2x
   conversion improvement; codec gains are not yet quantified. Export must wait
   for the current full revision rather than saving a stale processed buffer.
7. **AI and remaining heavy operations.** Reuse background-model sessions keyed
   by model/provider/thread settings, cache metadata and avoid redundant tile
   copies. Estimate ~1.2–1.5x warm background extraction; no large denoise CPU
   gain promised because inference dominates. Measure batch/thread/provider
   choices independently without changing numerical output. Optimize exact
   analysis/statistics/stacking copies only when meaningful benchmarks justify
   it; do not replace scientific measurements with preview approximations.

No Numba/Cython/Rust/C addition is proposed. Any such change, new dependency or
numerical tolerance requires approval after measurement and license review.

## Acceptance and unresolved scope

- Confirm local hardware as target and 6000 x 4000 BGR float32 as the acceptance
  case. Clarify whether <100 ms means median or p95 and whether it includes
  combined HSL/GHS/STF, zoomed ROI and background AI/full-worker contention.
- Proposed strict correctness baseline: bit-identical full pixels and dtype;
  approximate rendering only for preview. Separate scientific metric changes
  would require an agreed tolerance.
- Verify live GUI event-to-painted-frame latency on the target desktop after
  integration, in addition to isolated cProfile benchmarks.
- Existing tests: **88 passed**, one existing SpeechRecognition deprecation
  warning. No performance changes or additional dependencies yet.
