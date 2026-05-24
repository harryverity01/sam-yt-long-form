---
name: sam-yt-broll-director
description: Phase 2 of the sam-yt pipeline. Reads the base cut transcript from sam-yt-cutter and produces a structured b-roll plan — every visual slot specified with a creation brief, asset type, and cost estimate. Outputs broll_plan.json for sam-yt-broll-producer to execute. Never generates assets itself.
---

# sam-yt-broll-director (Phase 2)

## Job

Read the base cut transcript. Output a detailed plan that says: at this timestamp, put this kind of visual, made by this method, with this exact creation brief. Plus cost estimates and priority so low-value slots can be dropped if needed.

This skill does NOT generate any assets. It's the planning phase. Phase 3 executes the plan.

## Inputs

```
<project_dir>/edit/
├── base_cut.mp4               ← from sam-yt-cutter
└── master_transcript.json     ← word timestamps in output timeline
```

Optional:
- `<project_dir>/brief.md` — context for editorial decisions
- `<project_dir>/edit/project.md` — prior session memory

## Output

```
<project_dir>/edit/
├── broll_plan.json            ← structured plan (machine-readable, for Phase 3)
├── broll_plan.md              ← human-readable version (CHECKPOINT 2)
└── broll_plan_cost.md         ← per-slot cost estimates + total
```

## Cadence rules (the defaults)

Tuned for viral YouTube long-form. Override per-project if `brief.md` specifies otherwise.

| Position | Target visual change cadence | Rationale |
|---|---|---|
| 0–30s (hook) | every **5–8s** | Highest churn point. Dense visuals = retention. |
| 30s–end | every **8–15s** | Sustainable rhythm for long-form. |
| Last 30s | every **6–10s** | Re-engage drop-off. End on a peak. |

**Never let talking head run longer than 15s without a visual punch.**

For an 8-minute cut, expect roughly **35–50 b-roll slots**.

A "visual punch" doesn't have to be b-roll overlay. Valid options:
- Full-bleed b-roll cover
- Picture-in-picture / corner overlay
- Keyword caption stamp (lower-third or full-screen)
- Zoom punch-in on talking head (no overlay)
- Cam angle switch (if multi-cam talking head)
- Lower-third name/title card

Phase 3 has a budget — count "free" visual punches (caption stamps, zooms) against the cadence to reduce API spend.

## Slot classifier (the smart part)

For every phrase in the transcript, decide whether it needs a visual and what kind. Rules table:

| Trigger pattern in transcript | Asset type | Creation method |
|---|---|---|
| Named app/platform ("Instagram", "TikTok", "Notion") | App UI screenshot or scroll | Chrome MCP → screenshot |
| News claim ("there was an article", "headlines were saying…") | Headline screenshot stack | Web search top article → screenshot |
| Specific place mention ("Bali", "London", "the studio") | Google Earth flyover OR location photo | Manual / unsplash search |
| Product or tool name | Product page screenshot | Web search → screenshot |
| Statistic / number ("1 million views", "10x prices") | Number animation OR receipt screenshot | PIL counter OR screenshot if source exists |
| Person's name (their guest, mentor, etc.) | Their headshot OR a clip of them | YouTube search + clip extract |
| Quote / pull-quote ("if you can't make money while you sleep") | Karaoke caption animation | Remotion/PIL keyword sequence |
| Emotional peak word ("terrified", "every secret", "explosion") | Keyword caption stamp | PIL render, full-bleed or lower-third |
| Story claim with no specific referent ("kids on phones beating pros") | Concept video | Seedance text-to-video |
| Sam's own work/portfolio reference | Their IG/portfolio content | IG/YouTube download + clip |
| Generic concept needing visual ("money", "fear", "freedom") | Stock b-roll | Pexels API or Seedance |
| Hook moment with strong image ("hands shaking") | Cinematic concept clip | Seedance with detailed prompt |

## Per-slot output schema

Every slot in `broll_plan.json` must have:

```json
{
  "slot_id": 12,
  "output_start_s": 87.45,
  "output_end_s": 92.10,
  "duration_s": 4.65,
  "trigger_phrase": "I saw a kid with an iPhone getting more views than me",
  "trigger_words": ["kid", "iPhone", "more views"],
  "asset_type": "concept_video",
  "creation_method": "seedance",
  "creation_brief": "Vertical phone screen showing a teenager's hand holding an iPhone, fast-scrolling TikTok with viral view counts overlaid (50k, 200k, 1.2M). Phone glow lighting on face. Cinematic, slight slow-mo. 1920x1080 16:9. 4.5 seconds.",
  "placement": "full_bleed",
  "audio_handling": "duck_voice_no",
  "priority": "high",
  "estimated_cost_usd": 0.40,
  "fallback_if_fails": {
    "asset_type": "keyword_stamp",
    "creation_brief": "Full-screen UPPERCASE 'KID. iPHONE. MORE VIEWS.' in 3 progressive reveals"
  }
}
```

**`placement` options:** `full_bleed`, `pip_topright`, `pip_topleft`, `lower_third`, `centered_card`.

**`audio_handling`:** `duck_voice_no` (keep voice loud), `crossfade_into` (let asset audio play under), `silent_overlay` (mute asset's audio entirely).

**`priority`:** `critical` (drop this and the cut breaks), `high` (visually important moment), `medium` (nice-to-have visual punch), `low` (drop first if over budget).

## Pipeline (mandatory order)

### 1. Read transcript + base cut
- Probe `base_cut.mp4` duration
- Load `master_transcript.json` — word-level timestamps in output timeline
- Pack into phrase-level if not already (`pack_transcripts.py`)

### 2. Pass 1: identify all "must-cover" moments
Specific things the camera HAS to be off the talking head:
- Anything where the speaker references a specific external thing the viewer needs to see
- The actual viral payoff moment (their 1M view post if shown, etc.)
- Direct screen-content callouts ("look at this DM I got")

These are `critical` priority.

### 3. Pass 2: hook density
First 30s gets visual every 5–8s. If the speaker is dropping a tight monologue with no specific references, fill with:
- Keyword caption stamps on every emphasis word
- Cinematic concept clips that match the energy

### 4. Pass 3: pacing fill
Walk the transcript with a 15-second window. Any gap > 15s in the visual plan, add a `medium` or `low` priority slot.

### 5. Pass 4: closer punch
Last 30s revisits cadence to every 6–10s. Often a callback to an earlier visual works here.

### 6. Cost estimation
Sum estimated costs by `creation_method`:

| Method | Cost per slot | Notes |
|---|---|---|
| `seedance` (text-to-video) | $0.40 | 5-second clip at 1080p |
| `web_screenshot` | $0.00 | Chrome MCP, free |
| `google_earth` | $0.00 | Manual screen-record |
| `pexels_stock` | $0.00 | Free with API key |
| `keyword_stamp` (PIL) | $0.00 | Local render |
| `karaoke_quote` (PIL) | $0.00 | Local render |
| `youtube_clip` (yt-dlp) | $0.00 | Free |
| `ig_clip` (gallery-dl) | $0.00 | Free |
| `number_animation` (PIL) | $0.00 | Local render |
| `headshot_search` | $0.00 | Web search + download |
| `manual_lookup` | varies | User provides |

Total cost goes in `broll_plan.md` for user approval.

### 7. Write outputs
- `broll_plan.json` — full machine-readable plan
- `broll_plan.md` — human-readable: timestamp, what, why, cost
- `broll_plan_cost.md` — cost summary by category

### 8. CHECKPOINT 2 — wait for user
Show the user `broll_plan.md`. They can:
- Approve all
- Drop specific slots
- Change asset_type for a slot
- Add slots
- Re-prioritize

Common edits:
- "Drop all `low` priority Seedance to save $$"
- "Change slot 7 to a screenshot instead of generated"
- "Add a slot at 3:42 for the photo Sam mentions"

Re-write `broll_plan.json` with edits. Don't proceed without approval.

## Hard rules

1. **Never generate assets.** This skill only plans. Even if the user asks. Direct them to Phase 3.
2. **Every slot must have a `fallback_if_fails`.** Phase 3 will use it if API calls fail.
3. **Trigger phrase must match transcript exactly.** This is how Phase 3 knows where to put the asset.
4. **Estimate cost before showing user.** They need it for approval.
5. **Prioritize honestly.** Marking everything `critical` defeats the budget mechanism.

## Heuristics learned from Sam Ey Am

These came from the actual V8 build that worked:

- **Cold open visual matters most.** Sam opened with a 4-second IG profile reveal. Made the first 4 seconds feel "produced." Replicate this pattern: first slot is almost always a contextual asset, not a keyword stamp.
- **B-roll on emotional peaks, NOT on facts.** Facts are spoken. Visuals carry feeling. When Sam said "terrified" — keyword stamp. When he said "this is the principle of sharing" — let his face carry it.
- **One Seedance per major story beat, not per claim.** Generated video is expensive AND only works for non-specific imagery. Use it 5-10 times in an 8-min cut, not 20.
- **Quote moments deserve full karaoke treatment.** Sam's "if you can't make money while you sleep" needed the whole screen. ~7s sequence. Earns its real estate.
- **Number reveals (10x, 1M, 400→4000) need on-screen graphics.** Audience can't visualize numbers as fast as they hear them.
- **Callback visuals at the end.** If you showed the IG profile at 0:04, show a slight variant at 7:20 to close the loop.

## What this skill does NOT do

- Generate any actual b-roll (Phase 3)
- Render music (Phase 3)
- Render captions/subtitles (Phase 3 — though the plan specifies them)
- Compose final video (Phase 3)

Hand off `broll_plan.json` to Phase 3.
