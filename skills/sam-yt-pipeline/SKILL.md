---
name: sam-yt-pipeline
description: Top-level orchestrator for the sam-yt long-form video pipeline. Takes a project folder with raw 2-cam interview footage, chains sam-yt-cutter → sam-yt-broll-director → sam-yt-broll-producer, handles the two user checkpoints (viral cut selection + b-roll plan approval), reports cost and progress. Invoke this skill, not the individual phase skills, unless you want manual checkpoint control.
---

# sam-yt-pipeline (orchestrator)

## Job

Run the full sam-yt pipeline end-to-end on a project folder. Two confirmation checkpoints (viral cut, b-roll plan). Otherwise hands-off. Returns `final.mp4`.

## When to use this skill vs the individual phases

| Situation | Use |
|---|---|
| First time using these skills, want it to just work | `sam-yt-pipeline` (this skill) |
| Doing many videos, want full automation | `sam-yt-pipeline` |
| Got a base cut you like, want to redo b-roll | `sam-yt-broll-director` directly |
| Got b-roll plan, want to retry production | `sam-yt-broll-producer` directly |
| Debugging a phase | The phase skill directly |
| Want to checkpoint after Phase 1 to manually edit | Phase skills individually |

## Inputs

A project folder. That's it.

```
~/MyInterview/
├── raw/
│   ├── MAIN_cam.mp4
│   ├── BTS_cam.mp4
│   └── audio.wav        (optional)
└── brief.md             (optional, 1 paragraph context)
```

If no `brief.md`, the orchestrator asks the user a short clarifying question after probing the source files.

## Invocation

```
> /sam-yt-pipeline ~/MyInterview
```

Or in agent calls:
```
Run sam-yt-pipeline on ~/MyInterview
```

## Pipeline

### 1. Sanity check
- Confirm `<project_dir>/raw/` exists and contains ≥ 2 video files
- Confirm no `<project_dir>/edit/final.mp4` already exists (if yes, ask "rerun?" — don't overwrite silently)
- Check `verify_sync.py` is on PATH

### 2. Read brief if exists, otherwise ask
If `brief.md` missing, ask the user ONE question:

> "What's the most interesting thing in this interview — the moment that made you want to make a video of it? One sentence."

Save answer as `brief.md`. Then proceed.

### 3. Invoke Phase 1: sam-yt-cutter
Use the `Skill` tool to invoke `sam-yt-cutter` with the project directory.

Phase 1 will:
- Verify sources
- Transcribe
- Detect cam sync
- Propose 3 cut candidates
- **Wait for user to pick A/B/C**
- Assemble base cut

When Phase 1 returns: `<project_dir>/edit/base_cut.mp4` exists and `verify_sync.py` passed.

Show the user a 2-line summary:
> ✓ Base cut: N:SS minutes, warm_cinematic grade, sync verified
> ✓ Ready for b-roll planning. Proceeding to Phase 2...

### 4. Invoke Phase 2: sam-yt-broll-director
Use the `Skill` tool to invoke `sam-yt-broll-director`.

Phase 2 will:
- Read transcript
- Apply cadence rules (every 8–15s)
- Classify every slot
- Estimate cost
- Write `broll_plan.json` + `broll_plan.md`

Show the user the b-roll plan with cost summary:
> ✓ B-roll plan: N slots
>   - X Seedance generations (~$Y.YY)
>   - Z free renders (keyword stamps, screenshots)
>   - Total estimated: $TT.TT
>
> Review `edit/broll_plan.md` — approve, drop slots, or edit?

**Wait for explicit user approval.** Acceptable responses:
- "approved" / "go" / "ship it" — proceed
- "drop slot N" or "drop all low priority" — apply edit, show again, wait
- "change slot N to <method>" — apply edit
- "add slot at X:XX for <thing>" — add, show again

### 5. Invoke Phase 3: sam-yt-broll-producer
Use the `Skill` tool to invoke `sam-yt-broll-producer`.

Show progress updates every ~15 min:
> ⏳ Phase 3 progress: 12/47 assets generated, music queued, est. 90 min remaining

Phase 3 will:
- Generate assets in parallel batches
- Generate music
- Build master SRT
- Compose final
- Verify sync
- Self-eval up to 3 passes

### 6. Deliver
When Phase 3 returns:

> ✅ Done. Final video: `<project_dir>/edit/final.mp4` (N:SS, MM MB)
>
> Sync check: PASS
> Total spend: $TT.TT
> Wall time: H:MM
>
> Want me to play it? (opens in QuickTime)

Optionally offer:
- Open final.mp4 in default player
- Generate a YouTube title + description from the transcript
- Generate 3 thumbnail concept briefs

## Failure recovery

If any phase fails:

1. **Phase 1 fails:**
   - Source sync issues → tell user, suggest re-export
   - Transcription fails → check API key, retry once
   - User declines all 3 cut candidates → ask what they want, propose 3 more
   - Base cut fails sync → debug, this is a bug

2. **Phase 2 fails:**
   - Rare. Mostly editorial. Show user the partial plan, ask for guidance.

3. **Phase 3 fails:**
   - Individual asset fails → use fallback (already in plan)
   - Music fails → re-prompt ElevenLabs with simpler brief
   - Final compose fails → likely a render bug, surface to user with logs
   - Sync verification fails on final → re-render, usually fixes itself

In all cases: write what failed to `<edit>/project.md`, save intermediate state, surface to user with actionable next step.

## Progress reporting

Long phases (Phase 3 especially) should report progress. Use this pattern:

- Print one line when starting a phase
- Print one line per major sub-step (asset batch start, music generated, compose started)
- Don't spam — aim for ~10 progress lines per hour

If running in `--background` mode (future enhancement), poll for state changes every 5 min and surface via PushNotification.

## Cost guardrail

If total cost across all phases exceeds **$50**, pause before Phase 3 and re-confirm with user. Default cap can be overridden in `brief.md` with line:

```
max_cost_usd: 100
```

## Hard rules

1. **Never skip user checkpoints.** Even in full-auto mode, Phase 1 cut selection and Phase 2 plan approval are mandatory. The pipeline exists to save time, not to ship videos the user hasn't seen.
2. **Never overwrite an existing final.mp4 silently.** Ask first.
3. **Never proceed past a phase that didn't pass `verify_sync.py`.**
4. **Always write to `<project_dir>/edit/`.** Never anywhere else on disk.
5. **Update `<project_dir>/edit/project.md` at end of each phase.** Memory is the user's only audit trail.

## What this skill does NOT do

- Replace the individual phase skills (use them directly for fine-grained control)
- Publish to YouTube (out of scope, intentionally)
- Do thumbnails (separate skill, see `yt-thumb-generator` if installed)
- Handle multi-language transcription (defaults to English; pass `--lang` to Phase 1 if needed)

## Quick reference: when something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| Phase 1 says "all sources drifted" | Bad export from camera | Re-export from original SD card / NLE |
| Phase 1 cam_sync confidence < 0.5 | One cam was muted | Use single-cam mode |
| Phase 2 plan has too many Seedance | Transcript has lots of abstract concepts | Drop `low` priority slots manually |
| Phase 3 music sounds wrong | Brief was too vague | Edit `music/music_brief.md`, re-run Phase 3 step 5 only |
| Final has visible drift | Verify_sync missed it (rare) | Re-render Phase 3 with `--strict` flag |
| Captions hidden behind overlay | Render order bug | Re-render — subtitles must go LAST |
