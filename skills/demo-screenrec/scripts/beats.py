"""Auto camera: turn the layout plus each capture's action log into camera keyframes.

The rules are the reference video's grammar (see SKILL.md, "Camera grammar"):
  * a wide establishing shot with the desktop tilted (rotY -9, rotX 3.5) when a window opens
  * a push to 2.4x on every click, landing 0.2 s after the click, 0.9 s power2.inOut
  * 1.9x on a typing field for the whole typing run
  * 1.35x on the window for a scroll
  * back to wide when nothing happens for 2 s
  * the presenter framed at 86% of the width when no window is on screen

Keyframe semantics: `t` is the moment the camera ARRIVES; `dur` is the move's length.
"""
from common import load_json


def zoom_fit(rect, base_w, out, frac=0.86):
    """Zoom so that rect fills `frac` of the output width (or height if that binds)."""
    x, y, w, h = rect
    zw = frac * base_w / w
    base_h = base_w * out[1] / out[0]
    zh = frac * base_h / h
    return min(zw, zh)


def centre(rect):
    return [rect[0] + rect[2] / 2, rect[1] + rect[3] / 2]


def union(rects):
    x0 = min(r[0] for r in rects); y0 = min(r[1] for r in rects)
    x1 = max(r[0] + r[2] for r in rects); y1 = max(r[1] + r[3] for r in rects)
    return [x0, y0, x1 - x0, y1 - y0]


def auto_camera(project, actions_by_layer):
    base_w = project.get("base_w", project["canvas"][0] * 0.9)
    out = project["out"]
    duration = project["duration"]
    pres = project["presenter"]
    layers = project["layers"]
    keys = []

    def visible_rects(t):
        # the presenter card can leave the stage (presenter.out): a screen-only demo section
        rs = [pres["rect"]] if (pres.get("out") is None or t < pres["out"]) else []
        for L in layers:
            if L["in"] <= t and (L.get("out") is None or t < L["out"]):
                rs.append(L["rect"])
        return rs

    def wide(t, dur=1.0):
        rs = visible_rects(t)
        if len(rs) == 1 and rs[0] is pres["rect"]:
            # presenter alone: the reference's "full" framing
            return dict(t=t, target=centre(pres["rect"]), zoom=zoom_fit(pres["rect"], base_w, out, 0.86),
                        rotY=-2.5, rotX=1.2, dur=dur, ease="inOut", drift=0.03)
        if not rs:
            rs = [[0, 0, project["canvas"][0], project["canvas"][1]]]
        u = union(rs)
        # 0.80 leaves room for the tilt, which pushes the near edge outward
        z = min(zoom_fit(u, base_w, out, 0.80), 1.6)
        # tilt away from the presenter: if the presenter sits right, the left window comes forward
        pres_right = centre(pres["rect"])[0] > u[0] + u[2] / 2
        if len(rs) == 1 and pres["rect"] not in rs:
            # one window alone: frame it larger, tilt away from its centre
            z = min(zoom_fit(u, base_w, out, 0.86), 1.6)
        return dict(t=t, target=centre(u), zoom=max(z, 0.8), rotY=-9 if pres_right else 9, rotX=3.5,
                    dur=dur, ease="inOut", drift=0.025, wide=True)

    # establishing shot at t=0 (no move)
    k0 = wide(0.0, dur=0.0)
    keys.append(k0)

    events = []  # (t_project, kind, canvas point, layer, end)
    for L in layers:
        acts = actions_by_layer.get(L["id"])
        if not acts:
            continue
        sx = L["rect"][2] / acts["css"][0]
        bar = L.get("bar_h", 0)
        for e in acts["events"]:
            cx = L["rect"][0] + e["x"] * sx
            cy = L["rect"][1] + bar + e["y"] * sx
            events.append(dict(t=L["in"] + e["t"], kind=e["kind"], pt=[cx, cy], layer=L,
                               end=L["in"] + e.get("end", e["t"])))
    events.sort(key=lambda e: e["t"])

    # windows opening: wide shot arriving 1.0 s after the pop
    pres_out = pres.get("out")
    if pres_out is not None and pres_out < duration:
        # pull out while the presenter is still up, so the first window pops into a settled wide
        keys.append(wide(pres_out + 0.3, dur=0.9))
    for L in layers:
        if L["in"] > 0 and not (pres_out is not None and abs(L["in"] - pres_out) < 0.5):
            keys.append(wide(L["in"] + 1.0, dur=1.0))
        if L.get("out") is not None and L["out"] < duration:
            keys.append(wide(L["out"] + 0.9, dur=0.9))

    last_end = None
    last_push = None  # time the camera last pushed in on a point
    for e in events:
        if e["kind"] == "click":
            k = dict(t=e["t"] + 0.2, target=e["pt"], zoom=2.4, rotY=-4, rotX=2, dur=0.9, ease="inOut", drift=0.03)
        elif e["kind"] == "type":
            k = dict(t=e["t"] + 0.3, target=e["pt"], zoom=1.9, rotY=0, rotX=0, dur=0.9, ease="inOut", drift=0.02)
        elif e["kind"] == "scroll":
            # a scroll right after a push keeps the push (the reference scrolls while zoomed in)
            if last_push is not None and e["t"] - last_push < 3.0:
                last_end = max(last_end or 0, e["end"])
                continue
            L = e["layer"]
            k = dict(t=e["t"] + 0.2, target=centre(L["rect"]), zoom=min(zoom_fit(L["rect"], base_w, out, 0.92), 1.35),
                     rotY=-3, rotX=1.5, dur=0.9, ease="inOut", drift=0.0)
        elif e["kind"] == "hover":
            k = dict(t=e["t"] + 0.2, target=e["pt"], zoom=2.2, rotY=-4, rotX=2, dur=0.9, ease="inOut", drift=0.03)
        else:
            continue
        if e["kind"] in ("click", "type", "hover"):
            last_push = e["t"]
        # a wide shot must be seen before the first push: never merge it away, delay the push
        wides = [w for w in keys if w.get("wide") and w["t"] <= k["t"]]  # only wides already seen
        if wides and k["t"] - k["dur"] < wides[-1]["t"] + 0.8 and wides[-1]["t"] > k["t"] - 3.0:
            k["t"] = wides[-1]["t"] + 0.8 + k["dur"]
        # merge with a push that lands within 1.2 s, keeping the tighter shot
        if keys and not keys[-1].get("wide") and abs(keys[-1]["t"] - k["t"]) < 1.2 and keys[-1].get("dur", 0) > 0:
            if k["zoom"] >= keys[-1]["zoom"]:
                keys[-1] = k
        else:
            keys.append(k)
        last_end = max(last_end or 0, e["end"])
        # return to wide when the next event is more than 2.6 s away
        nxt = [x for x in events if x["t"] > e["t"]]
        gap = (nxt[0]["t"] if nxt else duration) - e["end"]
        if gap > 2.6 and e["end"] + 1.2 < duration:
            keys.append(wide(e["end"] + 1.2, dur=1.0))

    keys.sort(key=lambda k: k["t"])
    # drop keyframes that arrive before the previous one's move has finished
    clean = [keys[0]]
    for k in keys[1:]:
        if k["t"] - k.get("dur", 0) < clean[-1]["t"] + 0.15:
            clean[-1] = k if k["t"] > clean[-1]["t"] else clean[-1]
        else:
            clean.append(k)
    return clean


if __name__ == "__main__":
    import sys, json
    project = load_json(sys.argv[1])
    acts = {L["id"]: load_json(L["actions"]) for L in project["layers"] if L.get("actions")}
    print(json.dumps(auto_camera(project, acts), indent=1))
