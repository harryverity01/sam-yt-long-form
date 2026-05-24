---
name: sam-yt-broll-producer
description: Phase 3 of the sam-yt pipeline. Executes the b-roll plan from sam-yt-broll-director by spawning parallel sub-agents to generate every asset (Seedance, screenshots, keyword stamps, etc.), generates emotional-arc music via ElevenLabs, composes final video with overlays + captions + music, runs sync verification. Outputs final.mp4.
---

# sam-yt-broll-producer (Phase 3)

## Job

Execute the b-roll plan. Generate every asset in parallel. Make the music. Compose. Verify. Ship.

This is the longest phase (~2–3 hours wall time) and the most parallelism-heavy. Most of that time is waiting on Seedance and music APIs — actual compute is light.

## Inputs

```
<project_dir>/edit/
├── base_cut.mp4               ← from Phase 1
├── master_transcript.json     ← from Phase 1
└── broll_plan.json            ← from Phase 2 (user-approved)
```

## Output

```
<project_dir>/edit/
├── assets/
│   ├── slot_001_<short_name>.mp4
│   ├── slot_002_<short_name>.png
│   └── ...
├── music/
│   ├── music_brief.md         ← what was sent to ElevenLabs
│   └── generated.mp3
├── captions/
│   └── master.srt             ← keyword stamps + sentence captions, output-timeline
├── preview.mp4                ← 720p fast preview (intermediate)
├── verify/
│   └── sync_report.txt
└── final.mp4                  ← THE DELIVERABLE
```

## Pipeline (mandatory order)

### 1. Sanity-check the plan
- Load `broll_plan.json`
- Verify every `output_start_s` < `output_end_s` < `base_cut` duration
- Verify no overlap between slots (or flag intentional overlaps)
- Calculate total cost. If > $50, confirm with user once more.

### 2. Spawn parallel sub-agents for asset creation
**Rule 10 from video-use applies: parallel sub-agents, never sequential.** Spawn N at once via the `Agent` tool — total wall time ≈ slowest asset.

Group by creation method, batch similarly. Suggested batches:

**Batch A: Free local renders (PIL)**
- All `keyword_stamp` slots
- All `karaoke_quote` slots
- All `number_animation` slots
- One sub-agent each, ~30s wall time per slot

**Batch B: Web screenshots (Chrome MCP)**
- All `web_screenshot`, `headline_screenshot` slots
- One sub-agent each, ~1–2 min per slot

**Batch C: Seedance text-to-video (Fal.AI)**
- All `concept_video` slots
- One sub-agent each, ~3–5 min per generation
- Apply consistent grade to all Seedance outputs post-render (matches base cut)

**Batch D: Manual downloads (yt-dlp, gallery-dl)**
- `youtube_clip`, `ig_clip` slots
- One sub-agent each, ~1 min per

**Batch E: Stock search (Pexels)**
- `pexels_stock` slots
- One sub-agent each, ~30s per

Spawn ALL of Batch A, B, C, D, E in a single message with multiple Agent tool calls. Wait for all to complete.

### 3. Sub-agent brief template
Every sub-agent gets a self-contained brief. Copy-paste pattern:

```
ONE JOB: build one b-roll asset.

OUTPUT PATH (exact): {asset_path}
RESOLUTION: 1920x1080 (or {placement_size} if PiP)
FPS: 25
DURATION: {duration_s} seconds (EXACT — pad or trim to match)
CODEC: H.264, yuv420p, CRF 18
AUDIO: silent (mux at -an) UNLESS audio_handling=crossfade_into

CREATION BRIEF:
{creation_brief from broll_plan.json}

TECHNICAL CONSTRAINTS:
- File must exist at OUTPUT PATH when you finish
- Duration must be within 50ms of {duration_s}
- ffprobe must confirm 1920x1080 (or specified size), 25fps
- Verify by running: ffprobe -v error -show_entries stream=width,height,r_frame_rate,duration -of default OUTPUT_PATH

DO NOT ASK QUESTIONS. If the brief is ambiguous, pick the most obvious
interpretation and proceed. Report only success/failure at the end.

IF YOU FAIL: write the failure reason to {asset_path}.failure.txt and exit.
The orchestrator will use the fallback_if_fails plan.
```

### 4. Handle failures
After all sub-agents finish:
- For each slot with no asset file, check for `.failure.txt`
- Trigger the `fallback_if_fails` plan from `broll_plan.json` (usually a keyword stamp)
- Spawn one more sub-agent batch for fallbacks
- If a `critical` slot fails even on fallback, STOP and ask user

### 5. Generate music
Build music brief from `master_transcript.json` emotional beats:

```python
# Map transcript moments to music intensity
# Pattern that worked for Sam Ey Am:
# - Intimate/mysterious (sparse strings) for setup
# - Building tension for problem
# - Frustration energy for tension peak
# - Emotional swell for turning point
# - Triumphant climax at payoff
# - Settling/teaching vibe for principle
# - Final peak + decrescendo for close

# Format: 12-row table with timestamp ranges + emotional descriptor
# Send to ElevenLabs Music Compose API as `music_length_ms = (base_cut_duration - 20) * 1000`
# (Stop music 20s before end so closer lands in silence)
```

Write `music/music_brief.md` showing what went to ElevenLabs (for debugging if vibe is wrong). User can re-generate by editing the brief.

### 6. Build master SRT
- `build_master_srt.py base_cut.mp4 + transcript → captions/master.srt`
- Caption style: 2-word UPPERCASE chunks, MarginV=35 (Hormozi defaults)
- Override per `brief.md` if user wants different style

### 7. Compose
Build the final composition EDL (different shape from Phase 1's cut EDL):

```json
{
  "base": "edit/base_cut.mp4",
  "overlays": [
    {"file": "edit/assets/slot_001.mp4", "start": 0.00, "duration": 4.0, "placement": "full_bleed"},
    {"file": "edit/assets/slot_002.mp4", "start": 17.0, "duration": 4.0, "placement": "full_bleed"},
    ...
  ],
  "audio_mix": {
    "voice_track": "edit/base_cut.mp4",
    "music_track": "edit/music/generated.mp3",
    "music_volume_db": -12,
    "music_end_at_s": 218.0
  },
  "subtitles": "edit/captions/master.srt"
}
```

Run `render.py` to compose. Order matters:
1. Extract base segments
2. Apply b-roll overlays (PTS-shifted per Rule 4)
3. Mix audio (voice + music ducked at -12dB)
4. Burn subtitles LAST (Rule 1 — never before overlays)

### 8. Verify
- `verify_sync.py final.mp4` — must pass
- `verify_sync.py preview.mp4` — must pass
- Sample 5 cut boundaries via `timeline_view.py`
- Check no subtitle is hidden by an overlay (sample 3 known overlay windows)
- Check first 2s, last 2s for grade + readability

### 9. Self-eval, up to 3 passes
If anything fails: fix → re-render → re-eval. Cap at 3 passes. If still failing, surface to user with specific failure list.

### 10. Persist
Append to `<edit>/project.md`:

```markdown
## Session N — YYYY-MM-DD (sam-yt-broll-producer)

**Slots generated:** N (M failed, used fallback)
**Music:** generated.mp3, M:SS at -12dB, ends at X:XX
**Final duration:** N:SS
**API spend:** ~$XX (Seedance $X, Music $X, Other $X)
**Sync verification:** PASS / FAIL (details)
**Final file:** edit/final.mp4 (NN MB)
**Notes:** <non-obvious decisions, what fell back, what was retried>
```

## Hard rules

1. **Subtitles burn LAST in the filter chain.** Rule 1 from video-use. Otherwise overlays hide them.
2. **Per-segment extract → lossless concat → overlays.** Never single-pass filtergraph.
3. **PTS shift on every overlay:** `setpts=PTS-STARTPTS+T/TB`.
4. **Parallel sub-agents.** Never sequential. Spawn one batch, wait for all, move on.
5. **Music ends 20s before final cut.** Closer needs silence.
6. **Run verify_sync.py on every intermediate AND final render.**
7. **Cost cap.** If estimated cost > $50, re-confirm with user before spawning Seedance batch.
8. **Apply Seedance outputs through same grade as base cut** so they don't look like AI bolted on.

## Failure modes

- **Seedance returns ugly/wrong output.** Use fallback (keyword stamp) and flag to user. Don't keep retrying.
- **ElevenLabs music misses the brief.** Generate up to 2 variants. User picks. Don't burn 5 generations chasing perfection.
- **Sync verification fails on final.** Most common cause: subtitles burned BEFORE overlays. Re-render with correct order.
- **An asset is the wrong duration.** Pad with the last frame held, or re-render. Don't ship asset that's clearly the wrong length.
- **Spend exceeds estimate by > 30%.** Stop, surface to user.

## What this skill does NOT do

- Decide what visuals to make (that's Phase 2)
- Plan structure or cadence (Phase 2)
- Pick the viral cut (Phase 1)
- Publish to YouTube (the user does that)

Hand off `final.mp4`. Done.
