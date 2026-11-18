# Labeled public-data gaze evaluation

## Scope and fixed protocol

This local evaluation uses the original **VideoAttentionTarget official test split**, released with Chong et al., *Detecting Attended Visual Targets in Video*, CVPR 2020. It measures agreement with human gaze-target annotations, separately from physical glasses streaming and networking results. It does not establish gaze accuracy on the glasses footage.

Sources:

- Original dataset and label format: https://github.com/ejcgt/attention-target-detection
- Author-linked archive: https://www.dropbox.com/scl/fi/x4uqgkwcfjk16l54hm69f/videoattentiontarget.zip?rlkey=5b626ifn2ppdahekfldlkg7nd&dl=1
- MTGS data split definitions: https://github.com/idiap/MTGS/blob/a2ce45f44ed73d86e89e16bffb6be7a9567e3052/mtgs/datasets/videoattentiontarget_temporal.py
- Existing local model configuration and source provenance: [PART_B.md](PART_B.md)

Before inference, freeze a sample of **50 unique annotated frames per test show**, using Python's seeded random sampling (`20261118`) on sorted paths. The 500 frames contain 1,197 person-frame labels. Keep every annotated track on each selected frame. Selection never uses predictions, detection success or gaze class. Training and validation labels are not loaded. This is a reproducible subset evaluation, not a full official benchmark score.

The downloader reads the archive index and retrieves only the test annotations and selected JPEG members using HTTP byte ranges. It validates ZIP CRC and records SHA256 hashes. Interrupted downloads resume using verified existing files. Raw images, labels and archive index remain under ignored `data/raw/accuracy/`.

## Unchanged deployment pipeline

Call the existing `MTGSEngine.process` on every selected image. Use the deployed 224 x 224 pixel scene input, FP32, up to four detected heads, detector confidence 0.6 and in-frame threshold 0.8. No threshold fitting or settings selection takes place on these test data. Ground-truth boxes never enter the model. Each prediction retains the pipeline's existing head detection, cropping, normalization, model and overlays.

Assign predictions to annotated heads one-to-one using IoU >= 0.5. Maximize the number of valid matches, then total IoU. Compare the pipeline's returned 10%-expanded head boxes with raw annotation boxes. This matching differs from benchmark evaluations that supply ground-truth boxes directly to the gaze model. Additional predictions on unannotated people cannot be called false positives.

## Metrics and denominators

- **Head detection recall:** matched annotated heads / all annotated heads. Misses include confidence, minimum-size and four-head-limit effects.
- **Conditional in/out accuracy:** correct in/out classifications / matched heads, at the unchanged 0.8 threshold. Also report balanced accuracy, class recalls and in-frame average precision.
- **Detection + in/out success:** matched heads with correct classification / all annotated heads. Missing detections count as failures.
- **Conditional normalized target error:** Euclidean distance between predicted heatmap peak and the human target, using x/image-width and y/image-height. Score matched ground-truth in-frame labels even if the predicted in/out class is wrong. Units are normalized image coordinates, not pixels or degrees, and not a fraction of the diagonal.
- **Joint target success at 0.1 and 0.2:** detected, classified in-frame and target error within tolerance / all ground-truth in-frame labels. Missing heads and incorrect out predictions count as failures.

For inside targets, clamp annotation coordinates to image boundaries before normalization, retaining original values in the frozen labels. In/out labels follow the original release: (-1, -1) denotes outside. Outside labels do not receive a target distance. Report per-show counts and scores alongside aggregate person-frame scores, since frames and tracks are correlated. Do not claim independent participants or use frame counts as an independent-subject sample size.

Runtime logs distinguish model loading/warm-up, pipeline timings and offline evaluation throughput. Sparse sampled images have no encoded playback frame rate and do not replace the measured 8 fps streaming trials. Do not run GPU evaluation while physical timing trials are active.

## Reproduction

From the project root:

```sh
python3 tools/prepare_gaze_accuracy.py
.tools/gaze-env/bin/python -m unittest discover -s tests -p test_gaze_accuracy.py -v
.tools/gaze-env/bin/python tools/evaluate_gaze_accuracy.py \
  --data data/raw/accuracy/vat-test-2026-11-18 \
  --output output/accuracy/vat-test-224-2026-11-18 \
  --scene-size 224 --device mps
```

The evaluation output directory must be new. Full predictions, heatmaps, per-label scores, timing and fixed-index annotated previews remain under ignored `output/accuracy/`. Green boxes and target circles in previews are human annotations; existing colored arrows are model predictions. Scene and head-model hashes, input hashes and evaluator hashes are saved in the summary. No application or Part A changes are required.

## Completed results

The 500-frame local run completed. See [the measured summary](../results/accuracy/vat-test-224-2026-11-18/README.md) for results and limitations. All 1,197 labels were scored, and metrics were independently recomputed from saved per-label rows.
