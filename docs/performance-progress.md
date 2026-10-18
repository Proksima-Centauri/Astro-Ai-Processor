# Performance implementation progress

Branch: `perf/application-baseline`. No new dependencies or Siril code.

## Step 1: exact numerical buffer optimization

Levels now reuse owned float buffers and omit identity arithmetic. Curve
conversion reuses its buffer and RGB curves use a single OpenCV LUT call.
Camera Raw clips owned buffers in place. Full processing precision, rounding,
channel selection and dtype behavior remain unchanged.

6000 x 4000 BGR float32 measurements on the baseline host:

| Scenario | Before | After | Latency reduction |
| --- | ---: | ---: | ---: |
| Neutral Levels (paired reference benchmark) | 998 ms | 622 ms | 38% |
| Active Levels (paired reference benchmark) | 1929 ms | 1737 ms | 10% |
| Neutral Camera Raw | 406 ms | 249 ms | 39% |
| Full pipeline + curve + viewer | 2956 ms | 2266 ms | 23% |

Reference tests retain the old Levels/GHS/curve algorithms. Results are checked
with exact array equality across multiple dtypes, channels and exceptional
values. Run benchmarks independently of tests to avoid CPU contention:

```sh
PYTHONPATH=. .venv/bin/pytest
PYTHONPATH=.:tests .venv/bin/python tests/benchmark_performance.py
```

## Step 2: intermediate preview cache and preview-only LUTs

New `processing/preview.py` caches source, color, GHS, Levels, curve input and
display stages. Parameter changes reuse upstream results. Document changes
invalidate through source keys and synchronous processing; temporary overrides
are deliberately invalidated on each preview. Before pixmaps are reused;
dialogs prepare the cache on opening. Levels/GHS LUTs approximate only preview.
Curve input is converted once per upstream change, not per dragged point.

Levels/Curves refresh timers coalesce events at 16 ms without restarting an
already scheduled frame. Parameter edits immediately invalidate full-worker
revisions so old results cannot replace the new preview. Screen stretch can use
a reduced sample; full-size stretch and export retain exact algorithms.

Actual changed-parameter events, offscreen BlendViewer (not unchanged repaint):

| Scenario | Before | After |
| --- | ---: | ---: |
| Curve event -> repaint | 284 ms | 24 ms |
| Curve Before/After event -> repaint | 298 ms | 25 ms |
| Active Levels + existing curve -> repaint | no matching baseline event | 81 ms |
| Active GHS + active Levels + curve -> repaint | no matching baseline event | 82 ms |

These are medians of 5 events. Initial cache construction is slower (123 ms in
one cold curve sample), so warming on dialog opening matters. No p95 or physical
desktop certification is claimed from five events. Standalone 20-event compute
benchmarks: curve ~1 ms, Levels ~56 ms, combined GHS ~78 ms before rendering.

Preview LUT approximation can produce up to two display codes in the tested
steep curve case. Tests bound GHS preview error separately; full outputs use no
preview approximation. New dependencies: none.
