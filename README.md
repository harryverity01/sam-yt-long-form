# Sam YT Interview Cutter — viral long-form pipeline

A series of Claude Code skills that turn a 1–2 hour 2-camera interview into a 5–10 minute viral YouTube long-form video. Modeled on the workflow that produced ["He Gave Away Every Secret In The Photography Industry"](https://youtu.be/example) (Sam Ey Am × Harry Verity).

## What it does

Drop raw camera files in a folder. Get a finished video back.

```
~/MyInterview/
├── raw/
│   ├── MAIN_cam.mp4         ← main camera (the "hero" shot)
│   ├── BTS_cam.mp4          ← BTS / wide angle (often has cleaner audio)
│   └── audio.wav            ← optional separate audio recorder
└── brief.md                 ← optional 1-paragraph about what makes this interview interesting
```

Then in Claude Code:

```
> /sam-yt-pipeline ~/MyInterview
```

The pipeline runs four phases. Two confirmation checkpoints. Otherwise hands-off.

```
raw cameras + audio
        ↓
   [Phase 1: sam-yt-cutter]            ~10 min
        ↓
base cut (talking head, audio-synced, colour graded)
        ↓
   ✋ CHECKPOINT 1: pick 1 of 3 viral cut candidates
        ↓
   [Phase 2: sam-yt-broll-director]    ~5 min
        ↓
b-roll plan (every visual slot specified)
        ↓
   ✋ CHECKPOINT 2: approve the plan
        ↓
   [Phase 3: sam-yt-broll-producer]    ~2-3 hr
        ↓
final.mp4  (b-roll + captions + music + sync-verified)
```

## Quickstart

**New to this?** → Read [QUICKSTART.md](./QUICKSTART.md) for a step-by-step walkthrough of your first run.

## Install

```bash
git clone https://github.com/harryverity01/sam-yt-skills ~/sam-yt-skills
cd ~/sam-yt-skills
./install.sh
```

Install does:

1. Checks `ffmpeg`, `ffprobe`, `yt-dlp`, `python3` on PATH
2. Installs Python deps (`uv sync` or `pip install -r requirements.txt`)
3. Symlinks the 4 skills into `~/.claude/skills/`
4. Prompts for API keys (ElevenLabs, Fal.AI) and writes to `.env`
5. Verifies all 4 skills are registered

## Required API keys

- **ElevenLabs** — Scribe transcription + music compose. ~$0.10/hr transcription, ~$0.30/track music.
- **Fal.AI** — Seedance text-to-video for generic concept b-roll. ~$0.40/clip.
- *(Optional)* **OpenAI / Anthropic** — only if you want fallback transcription. Default uses Scribe.

Stored in `.env` at the repo root. Never committed.

## The 4 skills

| Skill | Phase | What it does |
|---|---|---|
| `sam-yt-pipeline` | Orchestrator | Top-level skill the user invokes. Chains the 3 phases, handles checkpoints. |
| `sam-yt-cutter` | 1 | Transcribe + viral arc proposal + multi-cam assembly + colour grade |
| `sam-yt-broll-director` | 2 | Read transcript, classify every b-roll slot with creation brief |
| `sam-yt-broll-producer` | 3 | Generate assets in parallel + music + compose + verify |
| `sam-longform-cut` | Standalone | Pulls a raw call from the shared R2 bucket and cuts a trailer plus a 20-45 min long form. Sam only, filler and dead air stripped, zero drift. |

Each skill is self-contained. The orchestrator chains them but they can be invoked individually for checkpoint editing.

## Defaults (tuned for Sam-style content)

- **Aspect:** 16:9 1920×1080@25fps
- **Length target:** 5–10 minutes
- **Cam setup:** 2-cam (MAIN + BTS), BTS audio on MAIN video by default (BTS usually has cleaner sound)
- **B-roll cadence:** one visual change every 8–15s (denser first 30s for hook retention)
- **Caption style:** Hormozi-style 2-word chunks, UPPERCASE, white-on-outline, MarginV=35
- **Colour grade:** warm cinematic by default
- **Music:** baroque-modern strings, emotional-arc synced

All defaults can be overridden in `brief.md` per-project.

## How long does it take?

For a 90-min interview producing a 7-min cut:

| Phase | Wall time | API cost |
|---|---|---|
| 1: Cutter | ~10 min | ~$0.20 (Scribe) |
| 2: Director | ~5 min | ~$0.05 (LLM calls) |
| 3: Producer | ~2–3 hr | ~$15–25 (Seedance + music + screenshots) |
| **Total** | **~3 hr** | **~$20** |

Most of Phase 3 is parallel API calls — wall time depends on how many sub-agents Claude Code lets you spawn concurrently.

## Outputs

Everything lives in `~/MyInterview/edit/`:

```
edit/
├── transcripts/           ← cached Scribe JSON per source
├── takes_packed.md        ← phrase-level reading view
├── cut_candidates.md      ← the 3 viral candidates (checkpoint 1)
├── base_cut.mp4           ← end of Phase 1
├── broll_plan.json        ← (checkpoint 2)
├── broll_plan.md          ← human-readable version
├── assets/                ← per-slot generated b-roll
│   ├── slot_01_hook.mp4
│   ├── slot_02_screenshot.png
│   └── ...
├── music/
│   └── generated.mp3
├── master.srt             ← output-timeline subtitles
├── verify/                ← sync-check reports
├── preview.mp4            ← 720p fast preview
└── final.mp4              ← shipping cut
```

## Project memory

Each project keeps `~/MyInterview/edit/project.md` — appended every session. Strategy, decisions, what worked, what didn't. Survives across runs so the second pass on the same footage gets smarter.

## Credits

Built on top of the [video-use skill](https://github.com/anthropics/skills) (Anthropic) and lessons learned producing Sam Ey Am's first viral long-form. The 542ms-drift incident is documented in `helpers/verify_sync.py`.

## License

MIT. Use freely, ship freely. PRs welcome.
