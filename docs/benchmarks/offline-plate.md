# Offline plate baseline (2026-11-10)

Command: `python scripts/benchmark.py --source upstream/onshape-fsgen/examples/native/plate.fs --iterations 3`
using x64 CPython 3.11.9 on Windows. The FSGen source pin is
`eabcc02ba104005da3de869e613cefe53042fd98`.

| Stage | Samples (ms) | Median (ms) |
| --- | ---: | ---: |
| Compile semantic features | 3171.137, 22.758, 95.246 | 95.246 |
| Plan identical snapshots | 22.492, 18.448, 16.954 | 18.448 |
| Local OpenCascade validation | 271.914, 278.631, 456.864 | 278.631 |

The first compile includes import/startup cost. The 12-feature local part
validated as one solid with volume 23244.3849 mm³. These measurements exclude
browser startup, remote transport, Onshape regeneration, and native editability;
those remain unmeasured. The script prints raw samples and validates each run,
so results can be compared after future compiler changes.
