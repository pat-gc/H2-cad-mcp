# Native car replacement — live tab inventory, 2026-11-14

Root approved replacing the earlier generated custom car after the [source-built native Part Studio](native-car-full-source-REPORT.md) and [eight-occurrence Assembly](native-car-source-assembly-REPORT.md) passed live verification. All actions below used ordinary signed-in Onshape Browser controls in H2 CAD Test Project, document `4e078dec822b4e509616b1cb`, workspace `af0627de07264acf086e646a`.

## Exact old content checked before deletion

- Old `Part Studio 1`, element `45730d1931712e2c548fae00`, contained exactly one user feature: `h2MinimalCar` / `H2 Minimal Car 1`, feature `FUIJDiupfLqxcTc_0`, plus the four defaults. Its seven literal length parameters were 180, 90, 37, 130, 14, 12 and 4 mm, matching the approved conceptual car, and it showed eight generated Parts. No other user feature, variable studio or model annotation was present. [Pre-deletion screenshot](native-car-replacement-old-custom-car-before.jpg).
- Old `Assembly 1`, element `cb5c127f6a4b4eb2ab5838c9`, was the **empty default Assembly**, with `Instances (0)` and `Mate features (0)`. It was not a populated assembly of the custom car. Historical inventory in `docs/verification/native-car-test-target-2026-11-13.md` likewise records this. Root reviewed the distinction and confirmed this exact empty old tab was within the requested replacement. [Pre-deletion screenshot](native-car-replacement-old-empty-assembly-before.jpg).

The normal tab menu's Delete command removed only these two exact tabs. Neither required an additional confirmation dialog. After each action the tab disappeared from the document tab DOM. `Feature Studio 1`, element `39a2e2afc5bc43eea167e938`, was **preserved**. All other test tab IDs remained present: `9a062f0eef8bb961f8c84f8e`, `1926791d173990d5d45f70ef`, `3a4e8933dde1c594115a657f`, `db4cd489011c3f8dace7baca`, `eb0d7b23baa21737e89c0464`.

## Verified replacements after deletion

| New tab | Element | Post-deletion result |
| --- | --- | --- |
| [Car - Native FSGen](https://cad.onshape.com/documents/4e078dec822b4e509616b1cb/w/af0627de07264acf086e646a/e/9b8155a2839e649138dae95f) | `9b8155a2839e649138dae95f` | Connected, saved idle revision `8efd43323560b46ad4ab334f`; all 22 feature IDs **and full definitions byte-equal** to the pre-replacement verified car; eight loaded original body IDs `JID,JMD,JQD,JQH,JUD,JUH,JYD,JYH`; journal unresolved 0, extension guard false. [Actual screenshot](native-car-replacement-final-partstudio.jpg). |
| [Car - Native Assembly](https://cad.onshape.com/documents/4e078dec822b4e509616b1cb/w/af0627de07264acf086e646a/e/4b621d8d622b4d57863db2cb) | `4b621d8d622b4d57863db2cb` | Connected, saved idle revision `6b4e9b7d11d3be934e042480`; normal UI Instances 8 / Mate features 0. Read-only viewer mesh at that revision verified eight unique occurrence paths, all original body IDs sourced from native car element `9b8155a2839e649138dae95f`, all identity transforms. [Actual screenshot](native-car-replacement-final-assembly.jpg). |

The new tabs were renamed through their normal tab context menus. The original Feature Studio remains as a preserved historical source; the replacement native car does not rely on that custom feature. This closes the specific car replacement task. General source-to-assembly automation and mechanical mates remain separate implementation work.
