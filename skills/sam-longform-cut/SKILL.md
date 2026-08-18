---
name: sam-longform-cut
description: Turn a raw Sam Eye Am podcast, interview or group call into a YouTube trailer plus a 20-45 minute long-form cut. Pulls the source from Sam's shared R2 bucket, reads the word-level transcript, builds a Sam-only paper edit, strips filler, pauses and dead air, renders frame-exact from 4K with slow zooms, proves there is zero drift, and ships back to R2 with titles, chapters and a description. Use whenever Harry says Sam has posted a new interview or call, or asks for a trailer, a long-form cut, a masterclass, or "the most exciting part" from a Sam recording. Triggers on "sam's new interview", "sam posted", "shared R2", "cut this into a YouTube video", "make a trailer", "turn this call into a video", "sam long form". For 30-45s vertical clips use `sam-clips-engine` instead.
---

# Sam long-form: trailer + YouTube cut

Built on the Tobi Group Coaching 2 call, 14 Aug 2026. One raw 102-minute 4K call in, a
1-minute trailer and a 41-minute masterclass out, both frame-exact.

`sam-clips-engine` makes the vertical Shorts. This skill makes the two horizontal files.
They share a source and nothing else.

## What Harry always wants, without being told

1. The trailer first. The most exciting part, cut to about 60-90 seconds, hook first.
2. **The trailer goes at the FRONT of the long form**, with its music bed, and the long
   form drops its own cold open so the material is not heard twice. This is the shape of
   the last Sam long form (`SAM_YT_FULL_v8.1`) and Harry expects it without asking.
   `scripts/build_v2.py` does the splice by stream copy: no re-render, no extra
   generation loss, 20 ms crossfade at the audio join.
3. The long form second, 20 to 45 minutes, filler and pauses and dead air gone.
4. Sam's voice only. Nobody else's audio ships.
5. No music on the long form. Sam calls a bed elevator music. The trailer gets one.
6. No burned captions on either file.
7. Zero drift. Prove it before you send anything.

## 1. Find the source

Sam's bucket is `harry-shared`, a different account from Harry's `verity-video`. Creds are
in env: `SAM_R2_ENDPOINT`, `SAM_R2_ACCESS_KEY_ID`, `SAM_R2_SECRET_ACCESS_KEY`,
`SAM_R2_BUCKET`. Shoots live under `podcasts/<date>-<name>/`.

List the bucket by last-modified and take the newest folder. **Harry names the shoot from
memory and the name is often wrong** — he asked for "the Tony interview" and the file was
`Tobi Group Coaching 2`. Match on recency, not on the name, and tell him what you found.

The folder usually already holds a Whisper word-level transcript (`<name>.json`), an SRT,
a speaker map and a summary. Download everything small first, read it, and only then pull
the 16 GB master. A 12-thread ranged GET off R2 runs at about 125 MB/s, so 16 GB takes
about two minutes (`scripts/dl.py`).

## 2. Read before you cut

`scripts/timeline.py` prints one line per transcript segment with speaker and timecode.
Read the whole thing. It is 900 lines and it is the job. Everything after this is
mechanical; the choice of what to keep is not.

Measure the gaps too. On the Tobi call, 43 of 102 minutes were gaps over a second. That
number tells you immediately that the raw timeline cannot ship and the film has to be
rebuilt from blocks.

## 3. Write the plan

`plan.py` is the format. Blocks are source seconds:

```python
(2388.5, 2514.6, ('push', 1.00, 1.07), "PROOF: cutting word gaps by the waveform"),
```

`(t0, t1, zoom, label)`. Zoom is `('none',)`, `('static', k)` or `('push', k0, k1)`.

Rules that came out of the first build:

- **Cold open.** Take the two strongest proof moments, put them at the top, and add their
  source ranges to `BODY_DROPS` so the body does not repeat them.
- **One idea per block.** The label becomes the YouTube chapter, so write it as one.
- **Alternate the zoom.** A push, then nothing, then a static punch. Never two pushes in a
  row. Short emphatic lines get a static punch-in, not a move.
- **Drop ranges** carry the editorial judgement: platform-risk passages, unsupported
  claims, anything unkind about a person in the room. Comment each one with why.

## 4. Build the cut

```
python3 build_cut.py longform
python3 build_cut.py trailer
```

It selects Sam's words by overlap (containment silently drops boundary words), then:

- clamps runaway Whisper tokens to 3 seconds, or gap detection breaks
- drops `um`/`uh` and stutters
- splits into runs at any word gap over 0.34 s — that is the dead-air removal
- pads each run 0.10 s in front and 0.22 s behind, 0.34 s extra at a section end
- **never bleeds a neighbouring word in.** The run end is clamped to 0.05 s before the
  next word in the source, whoever said it. Without this the dropped filler comes back.
- strips a dangling connective off the end of a section, so no block ends on "and"
- frame-quantises, then merges anything that now overlaps

Then audit every edge before you render:

```
python3 scripts/edges.py     # first 5 and last 6 words of every block
```

Fix every trailing fragment in `plan.py` and rebuild. This pass took ~15 small edits on
the first build and it is the difference between a cut that sounds intentional and one
that sounds like a machine did it.

## 5. Render

```
python3 render_video.py longform     # 2 workers, resumable, verifies frame count
python3 render_audio.py longform     # numpy splice at exact sample offsets
python3 normalise.py longform        # loudnorm to -16 LUFS, length forced back
python3 assemble.py longform         # concat, assert frame count, mux
```

**48000 / 30 = 1600 samples per frame, exactly.** Quantise to frames first and the sample
count falls out exact. Extract the master audio to 48 kHz PCM once, in one continuous
resample, and splice from that. Keep PCM until the final mux — AAC priming stacks into
drift.

Seek per segment is `ss = (f0 - 0.5) / FPS`. Half a frame early lands squarely on frame
`f0`. This is safe on the source file; it is **not** safe on a concatenated cut.

Encoder on a 4-core box: `-preset veryfast -crf 18`, two jobs at `-threads 2`. That runs
about 19 fps aggregate, so 40 minutes of output takes about an hour. `-preset fast` halves
it for no visible gain on a talking head — the 4K HEVC decode ceiling is only 32 fps.

Zooms use `perspective` with `eval=frame`, never `zoompan`, which quantises to whole
pixels and judders. Static zooms crop in 4K first and keep the real resolution.

**Re-centre the crop.** Sam does not sit in the middle of frame. Pull a frame per block,
build a contact sheet, and look. On the Tobi call he sat at x≈0.42 the whole way, so the
crop centre is `CX, CY = 0.435, 0.440` in `render_video.py`. Measure it every shoot.

## 6. Prove it

```
python3 qc.py longform
```

For seven segments it renders source frames `f0-2 .. f0+2` through that segment's own
filter chain and reports which one the segment's first frame matches. **Every checkpoint
must land on 0.** Audio-to-audio measurement does not detect a picture-placement error.
Never tell Harry a cut is synced without this output. For anything else, use `av-drift`.

## 7. Trailer finishing

The trailer gets three things the long form does not.

**Open on the funniest or strangest moment**, not the biggest claim. On the Tobi call
that was Claude messaging him "help" and nothing else. Harry asked for that order
explicitly and he was right: the odd human beat outperforms the credential.

**Cut harder than the long form.** `TRAILER_TIGHT` in `plan.py` drops the gap threshold
to 0.18 s and the pads to 0.06/0.13. Then go through the beats word by word and add an
explicit drop range for every tic and every stretched filler sitting in a gap. Removing an
interior word only removes its audio if the hole it leaves is wider than the gap
threshold, which is why the tight threshold and the drop list work together.

**No captions on the trailer.** Harry rejected them on the Tobi build (14 Aug 2026): the
picture and the voice carry it, and burned words make it look like a Reel rather than a
YouTube teaser. `captions.py` stays in the skill for a vertical or silent-autoplay cut, but
the default trailer ships clean. It draws Archivo Black, all caps, white with a 9 px black
stroke, two or three words a screen, centred at y=838 so they clear his face and sit above
the handheld mic. This ffmpeg build has no `drawtext` (no libfreetype), so
captions are PIL-drawn PNGs overlaid as a sequence. Fetch the font from
`raw.githubusercontent.com/google/fonts` — the fonts.google.com download endpoint returns
HTML here.

Phrasing matters more than the font. Break on punctuation and on any pause over 0.20 s,
then break so a line ends on a content word and the glue word starts the next line.
Mechanical two-word pairs read as machine output.

**Music, trailer only.** Sam's standing preference is no music, so the long form ships dry.
For a trailer, generate a bed with ElevenLabs `/v1/music` and lay it in with
`mixmusic.py`, which measures the speech level over speaking regions only.
Fade in 1.2 s, out 2.5 s. Peak the mix at -1 dBFS.

**A trailer bed sits 9 dB under the voice, not 16 dB.** The 16 dB figure in
`feedback_music_bed_levels` is the long-form VO spec: over 40 minutes a loud bed wears you
out. A trailer is 50 seconds and it has to hit. Harry rejected the 16 dB trailer at v4:
"There's no music on the trailer or its so low i can't hear ir." `mixmusic.py` now picks
the number from the target (`SEP = {'trailer': 9.0, 'longform': 16.0}`); pass a third
argument to override.

Measure it off the finished file, not off the intermediate WAV. Decode the muxed audio,
mark speaking regions on the dry voice track, then read the mix in the silent regions.
That number is the bed on its own.

## 7b. Ship

Upload under `podcasts/<shoot>/edits/`. Write `YOUTUBE PACKAGE.md` next to it with:

- five title options for the long form, three for the trailer
- the full description with chapters, generated from the block labels and durations
- thumbnail direction, from a real frame, never a generated plate
- a publish-notes section listing what was cut for safety and why

Also write the as-cut transcript (`as_cut.py`). Sam reads it to check the cut before he
watches it.

## Deliverable

1920x1080, 30 fps, H.264 High, AAC 48 kHz stereo, -16 LUFS, true peak -1.5 dBTP.
No music, no captions burned in, no colour grade. Grade later with `studio-colour-grade`.

## Do not

- Do not ship anyone's audio but Sam's without recorded permission. Cut the questions;
  the answers stand on their own and it is both cleaner and safer.
- Do not add music.
- Do not publish a platform workaround. Keep the sales teaching around it and drop the
  workaround itself.
- Do not use `zoompan`, or `crop` with `eval` — `eval` does not exist in this build.
- Do not run more than two ffmpeg jobs at once.
- Do not seek by timestamp on a concatenated cut.
- Do not claim sync without `qc.py`.
