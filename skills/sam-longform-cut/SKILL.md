---
name: sam-longform-cut
description: Turn a raw podcast, interview or group call into a YouTube trailer plus a 20-45 minute long-form cut. Reads a word-level transcript, builds a host-only paper edit, strips filler, pauses and dead air, renders frame-exact from 4K with slow zooms, and proves there is zero drift before it ships. Use when someone hands over a long recording and asks for a trailer, a long-form cut, a masterclass, or "the most exciting part". Triggers on "cut this into a YouTube video", "make a trailer", "turn this call into a video", "long form cut". For 30-45s vertical clips use `sam-clips-engine` instead.
---

# Long-form: trailer + YouTube cut

One raw 102-minute 4K call in, a 1-minute trailer and a 41-minute masterclass out, both
frame-exact. That was the first real run and the numbers below come from it.

`sam-clips-engine` makes the vertical Shorts. This skill makes the two horizontal files.
They share a source and nothing else.

## Run it

```bash
mkdir my-shoot && cd my-shoot
cp -r /path/to/sam-longform-cut/scripts/* .
python3 init.py /path/to/raw_interview.mov
```

`init.py` finds ffmpeg, makes the folders and links your file to `src/source.mov`.
Every script after that runs from this folder and uses relative paths.

If the footage is in a bucket instead of on disk, set `R2_ENDPOINT`,
`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` and `R2_BUCKET`, then:

```bash
python3 dl.py "podcasts/2026-08-13-my-shoot/raw.mov" src/source.mov
python3 init.py src/source.mov
```

You need python3, ffmpeg, numpy, requests and boto3. An ElevenLabs key in
`ELEVENLABS_API_KEY` covers transcription and the trailer music bed.

## The house rules, applied every time

1. The trailer first. The most exciting part, cut to about 60-90 seconds, hook first.
2. **The trailer goes at the FRONT of the long form**, with its music bed, and the long
   form drops its own cold open so the material is not heard twice. This is the house
   shape. `scripts/build_v2.py` does the splice by stream copy: no re-render, no extra
   generation loss, 20 ms crossfade at the audio join.
3. The long form second, 20 to 45 minutes, filler and pauses and dead air gone.
4. Sam's voice only. Nobody else's audio ships.
5. No music on the long form. Sam calls a bed elevator music. The trailer gets one.
6. No burned captions on either file.
7. Zero drift. Prove it before you send anything.

## 1. Find the source

Point `init.py` at the file. That is the whole step when the footage is on disk.

If it is in a bucket, shoots live under `podcasts/<date>-<name>/`. List by last-modified
and take the newest folder. **Whoever asks will name the shoot from memory and the name
is often wrong.** On the first run the request was "the Tony interview" and the file was
`Tobi Group Coaching 2`. Match on recency, not on the name, and say what you found.

The folder often already holds a transcript, an SRT, a speaker map and a summary. Pull
everything small first and read it for orientation. **Do not cut from it.** It is almost
always Whisper, and its timings are not tight enough to cut on. Run step 2 anyway. Only
then pull the master. A 12-thread ranged GET runs at about 125 MB/s, so 16 GB takes
about two minutes (`scripts/dl.py`).

## 2. Transcribe with Scribe

```bash
python3 transcribe.py
```

**ElevenLabs Scribe, never Whisper.** This is not a preference. Every cut in this skill
lands on a word boundary, so the transcript's timings are the edit. Whisper's word times
drift by tens of milliseconds. At that error a cut clips the consonant off the front of a
word, or leaves the tail of an "um" you thought you removed. Scribe is tight enough to
cut on. If you only have a Whisper transcript, re-run Scribe over the audio anyway.

One call, diarized, so the speaker labels stay consistent across the whole recording.
Chunking the audio renumbers the speakers and the host stops being the same person
halfway through.

It writes `meta/<shoot>.json` as segments of words:

```json
{"segments": [{"start": 0.1, "end": 0.9, "text": "So the brain",
               "words": [{"word": "So", "start": 0.1, "end": 0.32,
                          "speaker": "speaker_0"}]}]}
```

A new segment starts on a speaker change or a silence of 0.8 s or more. Needs
`ELEVENLABS_API_KEY`.

## 2b. Read before you cut

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

- clamps a runaway token to 3 seconds, or gap detection breaks
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
Never call a cut synced without this output.

## 7. Trailer finishing

The trailer gets three things the long form does not.

**Open on the funniest or strangest moment**, not the biggest claim. On the first run
that was Claude messaging him "help" and nothing else. The odd human beat outperforms
the credential.

**Cut harder than the long form.** `TRAILER_TIGHT` in `plan.py` drops the gap threshold
to 0.18 s and the pads to 0.06/0.13. Then go through the beats word by word and add an
explicit drop range for every tic and every stretched filler sitting in a gap. Removing an
interior word only removes its audio if the hole it leaves is wider than the gap
threshold, which is why the tight threshold and the drop list work together.

**No captions on the trailer.** They were tried and cut on the first build: the picture
and the voice carry it, and burned words make it look like a Reel rather than a YouTube
teaser. `captions.py` stays in the skill for a vertical or silent-autoplay cut, but
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
out. A trailer is 50 seconds and it has to hit. The 16 dB trailer was rejected on the first run:
"There's no music on the trailer or its so low i can't hear ir." `mixmusic.py` now picks
the number from the target (`SEP = {'trailer': 9.0, 'longform': 16.0}`); pass a third
argument to override.

Measure it off the finished file, not off the intermediate WAV. Decode the muxed audio,
mark speaking regions on the dry voice track, then read the mix in the silent regions.
That number is the bed on its own.

## 7b. Ship

Put the finished files in `out/`. Write `YOUTUBE PACKAGE.md` next to them with:

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
