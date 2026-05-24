---
name: sam-yt-cutter
description: Phase 1 of the sam-yt pipeline. Transcribes 2-cam interview footage, auto-syncs cameras via audio cross-correlation, proposes 3 viral 5-10 minute cut candidates, assembles the chosen one as a colour-graded base cut. Outputs base_cut.mp4 + master_transcript.json ready for sam-yt-broll-director.
---

# sam-yt-cutter (Phase 1)

## Job

Turn raw 2-camera interview footage into a viral-shaped 5–10 minute talking-head cut with audio synced, colour graded, and ready for b-roll overlay.

## Inputs

```
<project_dir>/
└── raw/
    ├── MAIN_cam.mp4         ← main camera (hero shot, often boom-mic'd)
    ├── BTS_cam.mp4          ← BTS / wide angle (often cleaner audio)
    └── audio.wav            ← optional separate recorder
```

Optional: `<project_dir>/brief.md` — one paragraph on what makes this interview worth watching. Influences viral arc proposals.

## Output

```
<project_dir>/edit/
├── transcripts/
│   ├── MAIN_cam.json
│   └── BTS_cam.json
├── cam_sync.json                 ← detected offsets, drift
├── takes_packed.md                ← phrase-level reading view
├── cut_candidates.md              ← 3 viral cut proposals (CHECKPOINT)
├── chosen_cut.json                ← user's pick
├── base_cut.mp4                   ← THE DELIVERABLE (5-10 min, graded, synced)
├── master_transcript.json         ← word timestamps in OUTPUT timeline
└── project.md                     ← memory, appended per session
```

## Pipeline (mandatory order)

### 1. Verify sources
- `verify_sync.py <project>/raw/*.mp4 --max-drift-ms 40`
- **If any source is drifted, STOP.** Drift baked into source = drift in every downstream cut. Tell the user, suggest re-export from camera or original NLE.

### 2. Probe sources
- `ffprobe` every file: duration, resolution, fps, audio specs
- Identify which is MAIN (usually the longest / highest-bitrate)
- Identify which is BTS (other camera, similar duration)
- If `audio.wav` exists, treat it as the canonical audio source

### 3. Transcribe (cached)
- `transcribe.py <best_audio_source>` — only transcribe ONE source (the one with cleanest audio)
- Default: BTS cam audio (BTS usually has dedicated lavalier; MAIN often has only ambient or boom)
- If `audio.wav` exists, transcribe that instead
- `pack_transcripts.py --edit-dir <project>/edit` → `takes_packed.md`

### 4. Auto-detect camera sync
- `cam_sync.py MAIN.mp4 BTS.mp4 --samples 5 -o <edit>/cam_sync.json`
- Reports:
  - Mean offset (seconds): how much BTS leads/lags MAIN
  - Drift across file (ms): cumulative clock skew
- **Confidence < 0.5 on any sample → escalate to user.** Means audio cross-correlation couldn't find a clear match. Likely cause: BTS was muted at that sample point.
- **Drift > 40ms (one frame) → use multi-point correction.** Stretch BTS audio with atempo per segment instead of single global offset.

### 5. Propose viral cut candidates (CHECKPOINT 1)
Spawn an editor sub-agent with this brief (Agent tool, sub-agent type `general-purpose`):

```
You are picking the viral story arc inside this 2-hour interview transcript.

INPUTS:
  - takes_packed.md (phrase-level transcript, time-annotated)
  - brief.md (if exists, otherwise infer from content)
  - Target: 5-10 minute cut, single coherent narrative

PROPOSE 3 CANDIDATES. Each is a chronological-or-restructured selection
of phrases from the transcript with a clear shape:

  HOOK (0-30s)         — pattern interrupt, contrarian claim, or a specific
                         visceral image. NOT exposition.
  PROBLEM/TENSION      — what was painful/wrong before
  TURNING POINT        — the decision or moment that changed everything
  EXECUTION            — what they actually DID, with specifics
  PAYOFF/EVIDENCE      — the result, with proof (numbers, examples)
  TEACHING/CLOSE       — the principle, mic-drop line, or call to action

RULES:
  - Start/end times must be on word boundaries from the transcript
  - Working window per cut: 30-200ms padding
  - Prefer cuts at silence ≥ 400ms
  - Prefer takes without filler / restarts / verbal slips
  - Total runtime 5-10 minutes
  - Lead with the most "scroll-stopping" moment available

OUTPUT (markdown, no code blocks):

# Candidate A: <one-line viral angle>
Total: M:SS | Hook strength: 1-10 | Predicted thumbnail moment: <timestamp>

| Beat | src timestamp | quote |
|---|---|---|
| HOOK | [02:34-03:01] | "..." |
| PROBLEM | [12:18-13:45] | "..." |
...

WHY THIS IS VIRAL: 2-3 sentences

# Candidate B: ...
# Candidate C: ...

Then a single line: WHICH WOULD YOU PICK AND WHY (your editorial recommendation).
```

Write the sub-agent's output to `<edit>/cut_candidates.md`. **Show the user, wait for selection.** Don't proceed without explicit pick (A/B/C or "combine A and B").

### 6. Assemble base cut
Once user picks:

1. Build the EDL from chosen candidate's beat list. Snap every cut to word boundaries from the transcript, pad 50ms before first word / 80ms after last (default Sam values).
2. For each segment: extract MAIN video + BTS audio (shifted by `cam_sync.offset`), apply 30ms audio fades, apply colour grade.
3. Concat losslessly.
4. Build `master_transcript.json` with output-timeline timestamps (use `build_master_srt.py` as reference for the projection math).
5. `verify_sync.py base_cut.mp4` — must pass.

**Default colour grade:** `warm_cinematic`. Applied per-segment during extraction (never post-concat).

```
# warm_cinematic filter chain
curves=master='0/0.05 0.5/0.5 1/0.95',
eq=contrast=1.05:saturation=0.92,
colorbalance=rs=0.05:gs=0:bs=-0.05:rh=0:gh=0:bh=-0.03
```

### 7. Self-eval
- `verify_sync.py base_cut.mp4` (mandatory)
- Sample 5 cut boundaries via `timeline_view.py` if available
- Check first 2s + last 2s for grade consistency
- If anything fails: fix → re-render → re-eval. Cap 3 passes.

### 8. Persist
Append to `<edit>/project.md`:

```markdown
## Session N — YYYY-MM-DD (sam-yt-cutter)

**Sources:** MAIN_cam.mp4 (NN min), BTS_cam.mp4 (NN min)
**Cam offset:** BTS leads MAIN by X.XXs (drift Yms across file)
**Transcript:** N words, M phrases packed
**Cut candidates:** 3 proposed, user picked <A/B/C>
**Base cut:** N:SS, warm_cinematic grade, sync verified
**Notes:** <any non-obvious decisions>
```

## Hard rules (don't violate)

1. **Never transcribe MAIN if BTS has cleaner audio.** Transcribing twice doubles cost for the same words.
2. **Never propose cuts without user approval.** Always show 3 candidates and wait. Even in full-auto mode.
3. **Never skip verify_sync on the base cut.** Drift caught here saves Phases 2 and 3 from compounding it.
4. **Apply grade per-segment, never post-concat.** Re-encodes the whole video twice.
5. **Snap to word boundaries.** Never cut mid-word, even if the gap looks clean.
6. **Cache transcripts per source.** Re-running this skill should never re-call Scribe unless source files changed.

## Failure modes (what to do)

- **Both cameras drifted → no clean source.** Tell user to re-export from original NLE/SD cards.
- **BTS audio is louder than MAIN but lower quality (more ambient).** Use MAIN audio. Override with `--prefer-audio MAIN`.
- **Cross-correlation confidence < 0.5 everywhere.** Cameras might not have been recording simultaneously. Ask user.
- **No silent gaps ≥ 400ms for cuts.** Speaker is too fluent. Widen padding to 200ms and accept tighter cuts.
- **All 3 cut candidates feel weak.** Show user, ask if there's something specific in the interview they want featured.

## What this skill does NOT do

- B-roll planning (that's `sam-yt-broll-director`)
- Captions / keyword stamps (that's `sam-yt-broll-producer`)
- Music generation (that's `sam-yt-broll-producer`)
- Final composition (that's `sam-yt-broll-producer`)

This skill ends with a polished talking-head cut. Hand off to Phase 2.
