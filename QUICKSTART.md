# QUICKSTART — your first viral long-form

Run-through of what to expect on your first interview. Aimed at someone who's never used these skills before.

---

## Before you start (one-time, ~5 min)

```bash
git clone https://github.com/harryverity01/sam-yt-skills ~/sam-yt-skills
cd ~/sam-yt-skills
./install.sh
```

The installer will:
1. Check `ffmpeg`, `ffprobe`, `python3` are installed (Mac: `brew install ffmpeg python@3.11`)
2. Install Python dependencies
3. Symlink the 4 skills into `~/.claude/skills/`
4. Create a `.env` file from `.env.example`

Then open `.env` and paste your API keys:

```
ELEVENLABS_API_KEY=sk_...          # required — for transcription + music
FAL_KEY=...                         # optional — for AI-generated b-roll
PEXELS_API_KEY=...                  # optional — for stock footage
```

Get keys from:
- ElevenLabs: https://elevenlabs.io/app/settings/api-keys
- Fal.AI (Seedance): https://fal.ai/dashboard/keys
- Pexels: https://www.pexels.com/api/

---

## Your first interview (~3 hours wall time)

### Step 1 — set up the folder

```bash
mkdir ~/MyInterview
mkdir ~/MyInterview/raw
```

Copy your camera files into `raw/`:

```
~/MyInterview/raw/
├── MAIN_cam.mp4         ← your main "hero" camera shot
└── BTS_cam.mp4          ← your second angle (often has cleaner audio)
```

(Optional: `audio.wav` if you used a separate recorder. Optional: `~/MyInterview/brief.md` with one paragraph about what makes this interview interesting.)

### Step 2 — run the pipeline

Open Claude Code in any directory. Type:

```
/sam-yt-pipeline ~/MyInterview
```

Walk away for ~10 minutes.

---

### Checkpoint 1 — pick a viral cut (~10 min in)

Claude will come back with something like this:

> ✓ Transcription: 12,847 words, 423 phrases
> ✓ Cam sync: BTS leads MAIN by 0.529s (drift 2ms across 77min — stable)
> ✓ Ready: 3 viral cut candidates ready for review
>
> See `edit/cut_candidates.md`. Pick A, B, or C.

Open `~/MyInterview/edit/cut_candidates.md` in any editor. You'll see something like:

```
# Candidate A: "He gave away every secret in his industry"
Total: 7:21 | Hook strength: 9/10 | Predicted thumbnail moment: [2:34]

| Beat | src timestamp | quote |
|---|---|---|
| HOOK | [02:34-03:01] | "Everyone would come to me at festivals..." |
| PROBLEM | [12:18-13:45] | "I didn't want to create more competitors..." |
| TURNING POINT | [42:11-43:55] | "If you can't make money while you sleep..." |
| EXECUTION | [51:02-55:18] | "So I shared every secret..." |
| PAYOFF | [62:30-64:10] | "First video got a million views..." |
| CLOSE | [88:15-89:01] | "Make me rich, I'll make you rich." |

WHY THIS IS VIRAL: Opens with a contrarian admission (gatekeeping is normal in this industry, but I'm telling you why I stopped). Builds to a quotable life lesson. Ends on a transactional mic-drop. Hook line is visceral and specific.

# Candidate B: ...
# Candidate C: ...
```

Type back in Claude:

```
A
```

or

```
B, but swap the close from B for A's close
```

Claude will assemble the base cut. Takes another ~2-5 minutes. Walk away.

---

### Checkpoint 2 — approve the b-roll plan (~20 min in)

Claude returns with:

> ✓ Base cut: 7:21, sync verified, warm_cinematic grade
> ✓ B-roll plan generated: 41 slots
>   - 8 Seedance generations (~$3.20)
>   - 6 web screenshots (free)
>   - 14 keyword caption stamps (free)
>   - 5 IG/YouTube clips (free)
>   - 8 other (free)
> ✓ Estimated total spend: ~$22 (incl. music)
>
> Review `edit/broll_plan.md`. Approve or edit.

Open `~/MyInterview/edit/broll_plan.md`. Looks like:

```
## Slot 1 — Cold open  [0:00-0:04, 4s]
**Trigger:** Cold open before any speech
**Type:** IG profile reveal  (priority: critical)
**Brief:** Screen recording of subject's Instagram profile, zoom into pinned reel
**Cost:** $0 (uses your IG download)

## Slot 2 — Hook keyword  [0:12-0:14, 2s]
**Trigger:** "everyone would come to me"
**Type:** Keyword caption stamp  (priority: high)
**Brief:** Full-screen UPPERCASE "EVERYONE CAME TO ME"
**Cost:** $0

## Slot 3 — Photographers concept  [0:17-0:21, 4s]
**Trigger:** "at festivals... gatekeep it"
**Type:** Seedance text-to-video  (priority: medium)
**Brief:** Group of professional photographers huddled, whispering, dim lighting,
          slightly conspiratorial mood. Cinematic 1920x1080.
**Cost:** $0.40

...
```

You can edit the plan in chat:

```
Approved, but drop slots 17, 22, and 31 (the low-priority Seedance ones)
to save budget. Change slot 14 to a screenshot of the actual article
instead of generated.
```

Claude re-writes the plan, shows you the new cost, waits again.

When you're happy: `go` or `ship it`. Phase 3 begins.

---

### Walk away (~2-3 hours)

Phase 3 runs unattended. It will:
- Spawn 30-50 parallel sub-agents to make each asset
- Generate music via ElevenLabs
- Render keyword caption stamps
- Compose final video
- Verify sync
- Self-eval up to 3 passes

Periodic progress updates:

> ⏳ 12/41 assets done | music queued | est. 95 min remaining

---

### Delivery

```
✅ Done. Final video: ~/MyInterview/edit/final.mp4 (7:21, 178 MB)

Sync check: PASS
Total spend: $19.40
Wall time: 2h 38m
```

Open it. If you want changes:
- Want to change the music? Re-run Phase 3 step 5 only (edit `music/music_brief.md` first)
- Want different b-roll on a specific moment? Edit `broll_plan.json`, re-run Phase 3 step 2 for that slot
- Want to recut? Run Phase 1 again, pick a different candidate

---

## What's in your folder after a successful run

```
~/MyInterview/
├── raw/                          (untouched)
├── brief.md                      (one paragraph context)
└── edit/
    ├── transcripts/              (cached, never re-transcribes)
    ├── takes_packed.md           (phrase-level reading view)
    ├── cut_candidates.md         (the 3 you chose from)
    ├── chosen_cut.json           (the one you picked)
    ├── base_cut.mp4              (graded, synced talking head)
    ├── master_transcript.json    (word timestamps in output timeline)
    ├── broll_plan.json           (the approved plan)
    ├── broll_plan.md             (human-readable version)
    ├── assets/                   (every b-roll asset)
    ├── music/
    │   ├── music_brief.md
    │   └── generated.mp3
    ├── captions/
    │   └── master.srt
    ├── verify/
    │   └── sync_report.txt
    ├── preview.mp4               (720p version for QuickTime)
    ├── final.mp4                 (the deliverable)
    └── project.md                (decisions + memory across sessions)
```

---

## Common first-time issues

### "❌ DRIFT — your_source.mp4 exceeds 40ms threshold"
Your raw export has audio drift baked in. Re-export from your camera's SD card or original NLE. The skill refuses to edit on top of drifted source because the drift will propagate everywhere and be hard to fix.

### Phase 1 says "cross-correlation confidence < 0.5"
One of your cameras was muted or had no audio at the sample point. Try:
```
/sam-yt-pipeline ~/MyInterview --prefer-audio MAIN
```
to use MAIN camera audio only.

### Cost estimate is way higher than you expected
Phase 2 over-classified things as `concept_video` (Seedance is expensive at $0.40/clip). Tell Claude:
```
Convert all `low` and `medium` Seedance slots to keyword stamps instead.
```

### Music sounds nothing like what you wanted
The brief was too vague. Open `edit/music/music_brief.md`, rewrite to be more specific (mood, BPM, instruments, emotional arc). Re-run Phase 3 step 5.

### Final video has visible drift
Rare, but: run `verify_sync.py ~/MyInterview/edit/final.mp4 --strict` to confirm. If it actually drifts, this is a bug — file an issue with the sync report.

---

## Pro tips after your first few runs

1. **Write a good `brief.md`.** Even one sentence helps Phase 1 pick better cuts. Best brief I've seen: *"This is a 90-min interview with a wedding photographer who decided to give away all his industry secrets and went from $400/hr to $4000/hr in 18 months. The viral moment is when he says 'if you can't make money while you sleep, you'll work until you die.'"*

2. **Approve the b-roll plan with edits, not blindly.** The classifier is good but not perfect. Look at slot priorities — drop `low` to save budget, upgrade `high` to `critical` if a beat needs to land hard.

3. **Use `project.md` as your editorial diary.** Every session appends notes. After 5 projects, you'll see your own patterns and can override defaults in `brief.md`.

4. **The cam_sync.json is reusable across edits.** Once you've synced two cameras for one interview, you can hard-code that offset in subsequent edits of the same source.

5. **Don't fight the cadence rule.** Visual change every 8-15s is what works. If you find yourself approving lots of 20-30s talking-head stretches, the cut isn't holding viewer attention — recut Phase 1.

---

Questions? Issues? https://github.com/harryverity01/sam-yt-skills/issues
