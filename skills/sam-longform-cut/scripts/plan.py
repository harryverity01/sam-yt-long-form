# Tobi Group Coaching 2 -> Sam long-form YouTube cut + trailer
# All times are SOURCE seconds in "Tobi Group Coaching 2.mov".
# Blocks are Sam-led teaching. Remote participant audio is never kept.

FPS = 30
SR  = 48000
SPF = SR // FPS          # 1600 samples per frame, exact

# --- tightening constants -------------------------------------------------
GAP_SPLIT_ABOVE = 0.34   # a word gap longer than this becomes a cut
HEAD_PAD        = 0.10   # breath in front of a kept run
TAIL_PAD        = 0.22   # breath after a kept run
BLOCK_TAIL      = 0.34   # extra breath at the end of a section
MAX_WORD_LEN    = 3.0    # clamp runaway whisper tokens
MIN_RUN_WORDS   = 2      # drop 1-word orphan runs ("yeah", "okay")

# connectives never left dangling at the end of a section
TRAIL_STRIP = {"and", "so", "but", "or", "then", "the", "a", "an", "um", "uh"}

# --- filler / junk --------------------------------------------------------
DROP_TOKENS = {"um", "uh", "erm", "ehm", "mmm", "hmm"}
# standalone acknowledgements only removed when they are the whole run
ORPHAN_TOKENS = {"yeah", "okay", "yes", "yep", "right", "nice", "cool",
                 "gotcha", "sure", "exactly", "thanks", "go", "years"}

# --- the long-form masterclass -------------------------------------------
# (t0, t1, zoom, label)
# zoom: ('none',) | ('static', k) | ('push', k0, k1)
BODY = [
    (238.0,  247.2, ('none',),            "Q: do you have a second brain"),
    (249.8,  337.75, ('push', 1.00, 1.06), "what a second brain is: local corpus, transcripts, frames"),
    (412.6,  567.1, ('none',),            "brain -> agent manager -> CEO -> new sessions"),
    (979.9, 1153.50, ('push', 1.10, 1.00), "what goes into the brain: emails, skills, books, vectors, routines"),
    (1202.9, 1231.3, ('static', 1.12),    "how long this took: years"),
    (1244.4, 1283.9, ('none',),           "what it costs: Pro, subscriptions vs API"),
    (1289.8, 1301.9, ('static', 1.18),    "PUNCH: Claude is blind and deaf"),
    (1384.6, 1533.68, ('push', 1.00, 1.08), "client example: daily routine, carousel, fix the root cause"),
    (1549.0, 1573.0, ('none',),           "Claude Code plans, Codex executes"),
    (1713.3, 1799.3, ('push', 1.08, 1.00), "guardrails: platforms, bots, what can get you blocked"),
    (1852.0, 1858.7, ('none',),           "trust arrives in levels"),
    (1878.7, 1950.2, ('static', 1.10),    "email reputation: five a day, engagement, warm not blast"),
    (2072.6, 2145.9, ('push', 1.00, 1.10), "Instagram is my baby: the 200-comment mistake, consent"),
    (2190.1, 2261.7, ('none',),           "3,000 followers: recutting my own viral reels"),
    (2271.3, 2302.55, ('static', 1.12),    "the stack: Whisper, Gemini, HyperFrames, Photos app"),
    (2368.9, 2383.25, ('none',),           "where do you start: where am I spending time"),
    (2388.5, 2514.6, ('push', 1.00, 1.07), "PROOF: cutting word gaps by the waveform, not the audio"),
    (2569.2, 2603.7, ('none',),           "not your trade? research exactly how the experts do it"),
    (2672.5, 2757.6, ('push', 1.09, 1.00), "every business is code: SOPs, McDonald's, order of operations"),
    (2894.0, 2947.1, ('none',),           "voice intake: yap for ten minutes, he splits the work"),
    (2948.8, 2994.65, ('static', 1.10),    "context first: he has to know who the client is"),
    (2997.2, 3128.1, ('push', 1.00, 1.08), "the client lens: review before any irreversible step, 7/10"),
    (3154.8, 3186.7, ('none',),           "the CEO routine: every day it audits the business"),
    (3217.9, 3243.15, ('static', 1.12),    "no more dashboards, send it to Telegram"),
    (3258.7, 3301.30, ('none',),           "life-changing, and the time it just messaged me 'help'"),
    (3528.5, 3579.3, ('none',),           "every lead scored locally, 10 out of 10"),
    (3672.4, 3760.2, ('push', 1.00, 1.08), "how it is actually built: md files, vectors, routines, cleanup"),
    (3985.5, 4098.1, ('none',),           "starting a new business: research, next best step, authenticity"),
    (4497.5, 4629.2, ('push', 1.08, 1.00), "selling to people like me: the pain, follow first, two offers"),
    (4677.1, 4738.7, ('none',),           "warm outreach, not spam; quality before quantity"),
    (4825.8, 4870.9, ('static', 1.10),    "make content first: your profile is the proof"),
    (4881.1, 4916.55, ('none',),           "the post to make: flip the phone, show the screen, explain it simply"),
    (5222.8, 5383.35, ('push', 1.00, 1.07), "from zero: the most painful problem, low risk, working for free"),
    (5412.5, 5514.7, ('none',),           "results beat testimonials, and get yourself results first"),
    (5575.15, 5945.1, ('push', 1.06, 1.00), "the offer rebuild: stop selling the craft, sell the outcome"),
    (6005.8, 6044.1, ('static', 1.12),    "CLOSE: everything is connected. That is the brain."),
]

# ranges removed from inside a body block
BODY_DROPS = [
    (340.2,  386.0),   # used in the cold open
    (1156.0, 1193.0),  # used in the cold open
    (4594.0, 4602.5),  # "a way around" Meta's DM rules - platform risk
    (5251.5, 5263.0),  # unsupported "older people spend more" heuristic
    (5680.0, 5726.0),  # "they don't have money, darling" + the rambling niche list
]

# a cold open, cut from the two strongest proof moments
COLD_OPEN = [
    (344.70, 385.60, ('push', 1.00, 1.06), "COLD OPEN: Claude booked me a podcast with a stranger"),
    (1158.60, 1179.75, ('static', 1.10),   "COLD OPEN: it pings me to plug the SSD in"),
]

LONGFORM = COLD_OPEN + BODY

# --- the trailer ----------------------------------------------------------
# Opens on the "help" story. Tighter than the long form: see TRAILER_TIGHT.
TRAILER = [
    (3268.80, 3281.85, ('push', 1.00, 1.06), "it messaged me 'help' and nothing else"),
    (1167.45, 1179.80, ('static', 1.10),     "it pings me to plug the SSD in"),
    (344.66,  350.36, ('static', 1.06),      "Claude emailed a stranger"),
    (378.18,  385.32, ('push', 1.04, 1.00),  "now I have two podcast hosts"),
    (2198.22, 2206.05, ('static', 1.12),     "carousels went viral and got me clients"),
    (2674.34, 2682.44, ('none',),            "every business is code"),
    (442.08,  446.23, ('push', 1.00, 1.08),  "the third step: you are the CEO"),
    (6040.48, 6043.90, ('static', 1.14),     "everything is connected. That is the brain."),
]

# every one of these is a verbal tic or a stretched filler word sitting in a gap
TRAILER_DROPS = [
    (3270.78, 3272.06),   # "like ... like"
    (3273.80, 3274.62),   # "like" before "just help"
    (3275.22, 3276.22),   # stretched "and"
    (3276.94, 3277.76),   # stretched "and"
    (3278.34, 3278.94),   # "like" before "is someone stealing"
    (1176.14, 1177.40),   # stretched "and"
    (380.60,  382.05),    # "I think out of like five or 10" - weakens the claim
    (2201.20, 2201.48),   # "like" before the number
    (2203.28, 2204.94),   # "and stuff like that he so and"
]

# the trailer cuts harder than the long form
TRAILER_TIGHT = {
    "GAP_SPLIT_ABOVE": 0.18,
    "HEAD_PAD": 0.06,
    "TAIL_PAD": 0.13,
    "BLOCK_TAIL": 0.16,
}
