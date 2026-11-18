# Local gaze accuracy: fixed VideoAttentionTarget test subset

Completed November 18, 2026 on the laptop, after the physical comparison measurements ended. This is labeled public-data evaluation, separate from glasses-domain accuracy and physical streaming tests.

500 fixed test frames from 121 clips and all 10 official test shows contain **1,197 annotated people** (777 in-frame, 420 outside). Seed: 20261118, 50 frames per show, selected before inference. The existing pipeline runs unchanged at 224 x 224 pixel scene input, FP32, detector confidence 0.6, maximum four heads and in-frame threshold 0.8. Ground-truth boxes are used for scoring only. Test labels do not influence settings selection.

| Metric | Result | Denominator / scope |
| --- | ---: | --- |
| Head detection recall | 92.0% | 1,101 / 1,197 annotated heads, one-to-one IoU >= 0.5 |
| In/out classification accuracy | 76.7% | 845 / 1,101 matched heads |
| In/out balanced accuracy | 70.4% | Mean matched-class recalls |
| In-frame recall | 95.1% | 658 / 692 matched in-frame labels |
| Outside-frame recall | 45.7% | 187 / 409 matched outside labels |
| In-frame average precision | 0.8867 | Matched heads, continuous scores |
| Detection + correct in/out | 70.6% | 845 / all 1,197 labels, missed heads fail |
| Mean normalized target L2 | 0.1225 | 692 matched human-labeled in-frame targets |
| Median normalized target L2 | 0.0675 | Same 692 targets |
| Joint target success, error <= 0.1 | 55.2% | 429 / all 777 in-frame labels, requires detection + predicted inside |
| Joint target success, error <= 0.2 | 68.2% | 530 / all 777 in-frame labels, requires detection + predicted inside |

Normalized L2 uses x/image-width and y/image-height. It is not pixels, degrees or fraction of image diagonal. Target error includes matched true-inside cases predicted outside; joint success additionally requires the correct inside classification. Missing heads are excluded only from conditional metrics and remain failures in joint scores.

**Interpretation:** the detector covers most annotated people, but the model often labels outside-frame gaze as inside. Aggregate in/out accuracy hides this imbalance. Median target error is lower than the mean, reflecting a tail of larger localization errors. These results do not validate gaze correctness on glasses footage or imply full Part C completion. Per-show results are in `per-show.csv`; frames and tracks are correlated and are not independent participants.

The complete pipeline averaged 121.6 ms with p95 150.9 ms. Offline evaluation throughput was 7.43 images/s, including decoding, scoring and prediction writes, excluding model load and warm-up. These full-resolution TV images are sparse accuracy samples, with no encoded output fps. These timings do not replace the separate glasses 8 fps trials.

## Reproduce and inspect

See [the evaluation protocol](../../../docs/GAZE_ACCURACY.md) for exact commands, sources, matching and denominators. Full predictions, scored labels and fixed-index annotated previews are local in `output/accuracy/vat-test-224-2026-11-18/`. Raw inputs and frozen selection are local in `data/raw/accuracy/vat-test-2026-11-18/`. Model/input/code hashes are in `summary.json`. `verification.json` confirms the 500-frame cohort, all 1,197 label scores, recomputed metrics and raw-output hashes.

Source: Chong et al., *Detecting Attended Visual Targets in Video*, CVPR 2020, https://github.com/ejcgt/attention-target-detection. Existing setup/source details remain in `docs/PART_B.md`. This subset uses original official test labels and differs from gaze-only evaluations that supply ground-truth head boxes. Do not compare it directly with published full-test benchmark numbers.
