# CS536 Smart Glass Bonus Project - Initial Plan

Drafted September 11, 2026. Current direction: work solo, obtain the glasses from Prof Peng, and find access to an Android phone. No Android phone is available yet. Weekly time budget and AI application choice are still open. This is a proposal for discussion, not a commitment to a particular implementation.

October 5 update: the INMO AIR2 and Pixel 5 are available, and the actual Part A stream has been verified through the phone to the laptop over Wi-Fi. The original planning sections below are retained as historical proposals. The selected Part B direction is now gaze estimation for a person visible to the glasses' outward-facing camera, with a direction-arrow overlay; this feature has not been implemented in the Part A checkpoint.

## 1. Assignment requirements

Source: [cs536-bonus-smartglass.pdf](cs536-bonus-smartglass.pdf), all four pages. Requirements below come from the handout; design choices and internal targets in later sections are our proposals.

| Part | Points | Required outcome |
| --- | ---: | --- |
| A | 50 | Stream the glasses' camera into an Android application, with the streamed content also visible on a laptop. Demonstrate the three-device system in class. Use INMO Air 2 or Air 3 (spelled IMNO in the handout). The handout recommends streaming for more than one minute before moving to B. |
| B | 50 | Add one AI application: visual search, text translation, a computer vision task, or an instructor-approved DIY idea. Provide settings and runtime start, stop, and pause controls. Demonstrate in class. |
| C | 50 | Evaluate multiple real-world scenarios, including PAL3.0 and 5G. Each scenario needs 10+ runs, each at least 30 seconds, with more than one hour total. Measure networking, streaming, and application-specific performance. Preserve every run's raw traces, analyze them, and produce figures. |
| D | 50 | Identify a problem from C, implement one improvement, and evaluate it in the wild. A smaller preliminary evaluation is allowed. |
| E | 40 | A 4-6 page LaTeX report, 10pt, two columns, plus a 10-minute presentation and live demos. Use `\documentclass[sigconf,10pt]{acmart}` for the handout's specified format; it references ACM template version 2.20. |

- Teams may have one to four students. Points are divided equally among team members: the per-person ceiling is 240, 120, 80, or 60 respectively.
- Partial scope is allowed, and plans may change. The handout warns that the full project requires more work than all programming labs combined.
- Use a private GitHub repository during development. Preserve tags `BONUS-PartA`, `BONUS-PartB`, `BONUS-PartC`, and `BONUS-PartD` for completed parts.
- Trace processing scripts must be in a folder named `Bonus-PartC`.
- Submit the repository URL and give the grader access; the handout names collaborator `chunyip`. Alternatively, submit applicable `Bonus-PartA.zip` through `Bonus-PartD.zip` with a README. Raw logs need to be retained for possible requests, but are not required in the submission.
- A and B demos are required for those parts; a D demo is encouraged but optional.

| Official date in 2026 | Deliverable |
| --- | --- |
| September 25-October 16 | Register on Gradescope with one page listing members and planned parts. |
| November 16 | One-page progress report, remaining scope, and changes from registration. |
| November 30, 23:59:59 | Project submission and one-page summary of completed work and planned presentation/demo. |
| December 4 | In-class presentation and demo; technical report due before or on this date. |
| Before December 6 midnight | The handout states a no-penalty report window. Plan to finish by December 4 instead of relying on that wording. |

The handout says additional guidelines will follow. For project questions it specifies course staff email with subject prefix `CS536: BONUS`, or in-person discussion, rather than Ed Discussion. These are course directions for future student actions, not authorization to send messages or submit anything now.

## 2. Proposed scope and app

Provisional solo target: complete A, B, C, and E, then implement one focused D improvement if the baseline is stable. These correspond to up to 190 points without D and 240 with D, subject to grading. Keep one AI task and one language pair in the initial scope. If the team grows later, account for the division of credit.

My initial recommendation is a **smart-glasses sign translator**: look at a sign, recognize the text on the phone, translate it, and return a short readable result to the glasses. Start with one fixed language pair, provisionally English to Spanish, and short printed text. Choose a pair whose output someone on the team can evaluate.

This matches an explicitly listed B option and gives us concrete tasks for evaluation: time to a usable translation, recognition errors, translation usefulness, and correct handling of scenes with no text. It does not require training a model from scratch.

| Candidate | Benefit for this project | Additional work |
| --- | --- | --- |
| Sign translation - recommended starting point | Clear demo and repeatable text/no-text cases | OCR plus translation; need ground truth and a reviewer who understands the language pair |
| Object detection/tracking | Explicitly allowed; can focus on a small set of everyday objects | Model selection, annotated examples, and stable labels/tracks |
| Visual search or custom AI assistant | Flexible application concept | Search/service integration and result evaluation; DIY needs prior instructor approval |

Proposed technical starting point: native Android for the glasses and phone, phone-side OCR/translation, and a laptop receiver/viewer with Python analysis scripts. Select the video transport after the hardware spike; do not commit to a complex streaming stack before confirming camera access and connectivity.

Google provides Android [text recognition documentation](https://developers.google.com/ml-kit/vision/text-recognition/v2/android) and a [camera translation codelab](https://codelabs.developers.google.com/codelabs/mlkit-android-translate). These support using ML Kit as an initial phone-side candidate, not a guarantee of performance on our devices. Its [translation API](https://developers.google.com/ml-kit/language/translation/android) supports downloading language models before use. Run this integration in the smartphone app and review its [usage guidelines](https://developers.google.com/ml-kit/language/translation/translation-terms), including attribution, when selecting dependencies.

## 3. First milestone: prove the hardware and network path

Before extensive app work:

1. Working solo is the current assumption. Confirm available weekly hours, which glasses can be borrowed from Prof Peng, and access to an Android phone. Try an available loan from course staff, a lab, or someone you know before choosing a purchase; availability is unconfirmed. If a purchase becomes necessary, compare specific options after learning the glasses model and budget.
2. Install and launch a minimal app on the actual glasses. Verify developer access, RGB camera frames, orientation, supported frame sizes/rates, and drawing text on the display.
3. Send frames to the Android phone and show the received stream in our application.
4. Display that stream on the laptop. During development this can use the simplest supported connection; record whether it is mirroring or a separate stream.
5. Send a sample result from the phone back to the glasses. Confirm camera capture and the result display can operate together.
6. Sustain the complete stream for at least two minutes, save diagnostic logs, and recover from a deliberate disconnect.

The vendor's [AIR2 documentation](https://gitee.com/inmolens/docs/blob/master/README.en.md) describes native Android development and camera access. The [INMO developer portal](https://developer.inmolens.com/) provides AIR3 resources. Confirm the actual model and firmware before assuming the same APIs or setup apply to both.

Network feasibility is part of this milestone. Identify separately the glasses-to-phone link and the phone-to-laptop link. Confirm PAL3.0 authentication, endpoint reachability, and whether the phone can maintain its glasses connection while using cellular data.

A 5G run must carry the measured traffic over cellular. A local hotspot stream with mobile data enabled does not establish that. One candidate is to keep the glasses connection local and route the phone-to-laptop stream over PAL3.0 or 5G to a reachable receiver. Validate routing and report each link separately; confirm the intended topology with staff if needed. A relay may be necessary, but is not assumed or deployed in this plan.

The phone must support installing/debugging our app, a sustained glasses connection, and the intended experiment network route. The proposed ML Kit OCR and translation integrations currently require Android API 23 or above, but satisfying the SDK minimum alone does not prove streaming performance or connectivity compatibility. A cellular plan with 5G access is a separate experiment dependency; confirm whether the borrowed phone has service or another suitable test phone is available.

Until the phone arrives, use an Android emulator and recorded clips for phone UI, AI integration, and log-analysis development. Once available, a phone camera can also act as a temporary input. These substitutes do not fulfill the actual glasses-plus-physical-Android-phone demonstration requirement. Timebox setup work and revisit scope before registration if hardware access remains unresolved.

## 4. Build sequence and completion checks

| Stage | Work | Completion check |
| --- | --- | --- |
| A: streaming | Glasses capture, phone preview, laptop display, start/stop, connection status, reconnect, timestamps and byte counters | Actual three-device demo streams for over one minute; internal target is three five-minute runs without a crash. Save `BONUS-PartA`. |
| B: AI | Fixed language settings, OCR, translation, result return, start/stop/pause, no-text state, stale-result clearing | Demonstrate readable text, no text, blur, changed text, pause/resume, and disconnection. Save `BONUS-PartB`. |
| C: evaluation | Pilot runs, fixed baseline settings, field trials, analysis, plots | Required run counts and duration verified; raw traces map to figures and tagged code. Save `BONUS-PartC`. |
| D: improvement | Choose one measured issue, implement a focused change, compare against the baseline | Matched trials show the effect and tradeoffs, including a null result if no improvement is observed. Save `BONUS-PartD`. |
| E: communication | Maintain notes from the start; report, slides, demo script, reproducible README | Report meets format/length requirements; presentation and demos fit ten minutes. |

Build logging during A so that C can analyze actual system behavior without retrofitting instrumentation.

## 5. Proposed field experiment

Start with six scenario/network combinations, subject to actual coverage and access:

| Scenario | Network | Planned runs | Run duration |
| --- | --- | ---: | ---: |
| Campus office, stationary | PAL3.0 | 12 | 2 minutes |
| Same office, stationary | 5G | 12 | 2 minutes |
| Campus walking route | PAL3.0 | 12 | 2 minutes |
| Same campus route | 5G | 12 | 2 minutes |
| Home, stationary | Home Wi-Fi | 12 | 2 minutes |
| Same home location | 5G | 12 | 2 minutes |

This proposes 72 runs and 144 minutes of recording, leaving margin above the assignment minimum. Setup, travel, charging, and failed runs require additional time. Keep failed attempts in the dataset, and collect extra complete runs when necessary. Treat each row as a scenario for run counting.

Use the same sign set, language pair, video settings, and task sequence. Alternate network order within each location where practical. Compare networks within matched locations; differences between home and campus cannot be attributed only to the network. Record coverage, movement, lighting, settings, model version, and device state.

Measure:

- **Networking:** sent/received bytes per interval and per link, uplink/downlink throughput, RTT, connection failures, and recovery time. Distinguish application goodput from wire throughput where both are available.
- **Streaming:** delivered frame rate, frame gaps, stall count/duration, variation in arrival intervals, and capture-to-display delay. Define a stall threshold before the main trials and document it as our definition.
- **AI:** time from presenting a sign to the first usable translation, OCR character/word error against transcribed text, translation task success against a predefined rubric, no-text false positives, and stale-result duration after the scene changes.

Use monotonic clocks for durations on each device. Cross-device timestamps need clock-offset estimation and an uncertainty estimate; do not subtract unrelated device clocks or treat RTT/2 as a measured one-way delay. An externally recorded timer experiment can validate end-to-end display delay.

Each run should save a manifest, code tag/commit, configuration, network route/interface, events, frame IDs, capture/send/receive/display timestamps where available, byte counters, AI timing/results, errors, and available packet traces from controlled endpoints. Packet-capture availability on the phone/glasses must be checked in the pilot. Packet traces and app events serve different purposes; keep both where available.

Planned figures: latency distributions by condition, throughput and stalls over time, AI response time and accuracy/task success, and baseline-versus-enhancement comparisons. Show variation across independent runs rather than treating every video frame as an independent experiment.

## 6. Part D: choose after looking at C

Possible changes, not predetermined findings:

- If network congestion causes stalls: adapt video bitrate or frame rate using observed queueing/throughput, and measure the OCR-quality tradeoff.
- If AI processing makes displayed results old: adjust frame selection or processing frequency while measuring translation accuracy and result age.
- If changing OCR output makes the overlay flicker: stabilize repeated observations and measure both readability and added delay.

Keep essential correctness, bounded queues, and basic failure handling in the baseline. D should address an observed limitation rather than deliberately omitting basic functionality from A/B.

For preliminary evaluation, a candidate budget is two relevant conditions x six runs x two versions x two minutes = 48 minutes. Alternate baseline/enhanced runs and keep other settings fixed.

## 7. Proposed schedule

These internal milestones can change with hardware availability and the team's time budget.

| Dates, 2026 | Target |
| --- | --- |
| Sep 11-24 | Arrange glasses and an Android phone; confirm solo time budget; complete camera, display, connectivity, and logging spike if hardware is available. |
| Sep 25-Oct 2 | First reliable A demo; prepare registration early in the window. |
| Oct 3-16 | Complete B prototype and submit registration by Oct 16. |
| Oct 17-30 | Stabilize A/B, pilot metrics, fix logging, and freeze baseline configuration. |
| Oct 31-Nov 13 | Main C field trials and analysis. |
| Nov 14-16 | Review evidence; submit the Nov 16 progress page and select D scope. |
| Nov 17-23 | Implement/evaluate D; draft report figures and conclusions. |
| Nov 24-29 | Reproducibility check, tags, README, report/slides drafts, submission page. |
| Nov 30 | Submit project materials by 23:59:59. |
| Dec 1-3 | Rehearse full ten-minute presentation and live demos; finish report. |
| Dec 4 | Presentation, demos, and report. |

If the actual hardware stream is still blocked at registration close, explicitly reduce or revise scope. If the baseline is unstable by the Nov 16 check, prioritize completed parts and reliable evidence over a broad D feature.

## 8. Proposed repository layout

Part A source code now exists in `glasses-app/`, `android-app/`, `android-common/`, `stream-core/`, and `laptop-viewer/`, with development tools and tests. See `README.md` for build/run instructions and `docs/HARDWARE_CHECKLIST.md` for the pending physical-device checks. The following remains the broader proposed layout for later parts:

```text
Bonus_Project/
  cs536-bonus-smartglass.pdf
  PROJECT_PLAN.md
  README.md
  glasses-app/
  android-app/
  laptop-viewer/
  Bonus-PartC/
  experiments/            # protocols, run manifests, ground truth
  data/raw/              # retained outside Git, backed up separately
  results/               # derived tables and figures
  report/                # LaTeX source and bibliography
  presentation/
```

Next decisions: weekly effort for solo work, Android phone and cellular access, actual glasses model, translation versus another AI task, and which parts to target in registration. The first technical work should be the hardware feasibility spike, followed by the streaming prototype.
