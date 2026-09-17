"""Build one demo from a project.json: cut the studio footage, capture every window,
derive the camera, render the stage, mux the audio.

    python build.py project.json [--recapture] [--camera camera.json]

project.json (see SKILL.md for the full schema):
{
 "name": "cowork-routine",
 "fps": 25, "out": [1920,1080], "canvas": [3840,2400], "base_w": 3456,
 "wallpaper": "assets/wallpaper.png",
 "studio": {"src": "/path/cam1.mp4", "start": 236.72, "end": 252.30},
 "presenter": {"rect": [2400,1250,1000,562], "radius": 28},
 "layers": [
   {"id": "routines", "capture": {"steps": "steps_routines.json"},
    "pos": [140, 180], "in": 2.0, "out": null, "chrome": "traffic", "title": "Routines"}
 ],
 "camera": "auto",
 "hud": [{"kind": "pill", "text": "Routines", "in": 2.4, "out": 6.4}]
}
Everything relative resolves against the project file's folder.
"""
import argparse
import os
import subprocess
import sys

from common import load_json, probe_frames, save_json, x264_args

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def sh(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--recapture", action="store_true")
    ap.add_argument("--camera", help="use this camera.json instead of auto")
    ap.add_argument("--preview", type=float, help="render only the first N seconds")
    ap.add_argument("--chunks", type=int, default=1, help="render the stage in N parallel processes")
    args = ap.parse_args()

    pdir = os.path.dirname(os.path.abspath(args.project))
    os.chdir(pdir)
    P = load_json(args.project)
    fps = P.get("fps", 25)
    P.setdefault("out", [1920, 1080])
    P.setdefault("canvas", [3840, 2400])
    P.setdefault("base_w", 3456)
    os.makedirs("cut", exist_ok=True)
    os.makedirs("out", exist_ok=True)

    # 1. studio cut: presenter video (1080p, frame-exact) and its audio from the same cut
    st = P["studio"]
    n_frames = int(round((st["end"] - st["start"]) * fps))
    P["duration"] = n_frames / fps
    pres_mp4, aud = "cut/presenter.mp4", "cut/audio.wav"
    if not os.path.exists(pres_mp4) or probe_frames(pres_mp4) != n_frames:
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{st['start']:.3f}", "-i", st["src"], "-frames:v", n_frames,
            "-vf", f"fps={fps},scale=1920:1080:flags=lanczos", "-an"] + x264_args(14) + [pres_mp4])
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{st['start']:.3f}", "-i", st["src"], "-t", f"{n_frames / fps:.6f}",
            "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", aud])
    got = probe_frames(pres_mp4)
    assert got == n_frames, f"presenter cut has {got} frames, want {n_frames}"
    P["presenter"]["src"] = pres_mp4
    P["presenter"].setdefault("in", 0.0)

    # 2. captures, or clips lifted from an existing screen recording / video
    for L in P["layers"]:
        cap = L.get("capture")
        clip = L.get("clip")
        if clip:
            # {"src": video, "start": s, "duration": s, "crop": [x,y,w,h]} -> frame-exact 25 fps cut
            out = f"cut/{L['id']}.mp4"
            n = int(round(clip["duration"] * fps))
            vf = (f"crop={clip['crop'][2]}:{clip['crop'][3]}:{clip['crop'][0]}:{clip['crop'][1]}," if clip.get("crop") else "") + f"fps={fps}"
            if args.recapture or not os.path.exists(out) or probe_frames(out) != n:
                sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{clip['start']:.3f}", "-i", clip["src"], "-frames:v", n,
                    "-vf", vf, "-an"] + x264_args(14) + [out])
            L["kind"] = "video"
            L["src"] = out
            w = clip["crop"][2] if clip.get("crop") else L["rect"][2]
            h = clip["crop"][3] if clip.get("crop") else L["rect"][3]
            scale = L.get("scale", 1.0)
            bar = int(L.get("bar_h", 76)) if L.get("chrome") == "traffic" else 0
            L["bar_h"] = bar
            L["rect"] = [L["pos"][0], L["pos"][1], int(w * scale), int(h * scale) + bar]
            L.setdefault("cursor", False)
        if cap:
            cdir = f"cap/{L['id']}"
            if args.recapture or not os.path.exists(f"{cdir}/actions.json"):
                sh([PY, os.path.join(HERE, "capture_web.py"), cap["steps"], cdir])
            L["kind"] = "frames"
            L["dir"] = f"{cdir}/frames"
            L["actions"] = f"{cdir}/actions.json"
            meta = load_json(L["actions"])
            w = meta["css"][0] * meta["dpr"]
            h = meta["css"][1] * meta["dpr"]
            bar = int(L.get("bar_h", 76)) if L.get("chrome") == "traffic" else 0
            L["bar_h"] = bar
            L["rect"] = [L["pos"][0], L["pos"][1], w, h + bar]
        L.setdefault("in", 0.0)
        L.setdefault("out", None)

    # 3. camera
    if args.camera:
        keys = load_json(args.camera)
    elif P.get("camera") == "auto" or not P.get("camera"):
        sys.path.insert(0, HERE)
        from beats import auto_camera
        acts = {L["id"]: load_json(L["actions"]) for L in P["layers"] if L.get("actions")}
        keys = auto_camera(P, acts)
        save_json("cut/camera_auto.json", keys)
        print(f"camera: {len(keys)} keyframes -> cut/camera_auto.json")
    else:
        keys = P["camera"]
    save_json("cut/project_resolved.json", P)

    # 4. stage render
    vid = f"out/{P['name']}_video.mp4"
    if args.chunks > 1 and not args.preview:
        # parallel chunks on whole-frame boundaries, then a re-encoded join (a -c copy concat of
        # x264 segments carries DTS jumps that drop frames downstream)
        save_json("cut/camera_used.json", keys)
        total = n_frames
        bounds = [round(i * total / args.chunks) for i in range(args.chunks + 1)]
        procs, parts = [], []
        for i in range(args.chunks):
            part = f"out/chunk_{i:02d}.mp4"
            parts.append(part)
            cmd = [PY, os.path.join(HERE, "stage.py"), "cut/project_resolved.json", "cut/camera_used.json", part,
                   f"{bounds[i] / fps:.6f}", f"{bounds[i + 1] / fps:.6f}"]
            print("$", " ".join(cmd), flush=True)
            procs.append(subprocess.Popen(cmd, stdout=open(f"out/chunk_{i:02d}.log", "w"), stderr=subprocess.STDOUT))
        for i, pr in enumerate(procs):
            if pr.wait() != 0:
                raise SystemExit(f"chunk {i} failed, see out/chunk_{i:02d}.log")
            got = probe_frames(parts[i])
            assert got == bounds[i + 1] - bounds[i], f"chunk {i} has {got} frames, want {bounds[i + 1] - bounds[i]}"
        with open("out/concat.txt", "w") as f:
            for part in parts:
                f.write(f"file '{os.path.basename(part)}'\n")
        sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "out/concat.txt", "-an"] + x264_args(16) + [vid])
        n = probe_frames(vid)
        assert n == total, f"joined video has {n} frames, want {total}"
    else:
        from stage import render
        n = render(P, keys, vid, t1=args.preview)
    print(f"stage: {n} frames")

    # 5. mux
    final = f"out/{P['name']}.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-i", vid, "-i", aud, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-shortest", final])
    print(f"done: {os.path.abspath(final)}")


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    main()
