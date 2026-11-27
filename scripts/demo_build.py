"""Build the demo video from the recordings. Usage: python scripts/demo_build.py WORKDIR DECK_PDF OUT.mp4
Parts: slide 2, live Hindi round (A), live English round (B), slides 7, 9, 14. Each part gets a burned-in
caption strip; the live parts also have the narration and the (synthetic) answer clips mixed in."""

import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from demo_texts import TEXTS

W, PDF, OUT = sys.argv[1:4]
PAD = "0xfff8ec"


def run(*a):
    subprocess.run(list(map(str, a)), check=True)


def dur(path):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]))


def srt_time(t):
    return f"{int(t // 3600):02}:{int(t % 3600 // 60):02}:{int(t % 60):02},{int(t % 1 * 1000):03}"


def build(part, video, cues, length, still=None):
    srt = f"{W}/{part}.srt"
    with open(srt, "w") as f:
        n = 0
        for c in cues:
            if c["kind"] != "nar":
                continue
            n += 1
            end = c["t"] + dur(W + "/nar/" + c["name"] + ".mp3")
            f.write(f"{n}\n{srt_time(c['t'])} --> {srt_time(end)}\n{TEXTS[c['name']][1]}\n\n")
    ins, fl, labels = [], [], []
    vin = ["-loop", "1", "-framerate", "25", "-i", still] if still else ["-i", video]
    for i, c in enumerate(cues):
        path = f"{W}/nar/{c['name']}.mp3" if c["kind"] == "nar" else f"{W}/{c['dir']}/{c['name']}.wav"
        ins += ["-i", path]
        ms = int(c["t"] * 1000)
        fl.append(f"[{i + 1}:a]aresample=44100,aformat=channel_layouts=mono,adelay={ms}:all=1[{c['kind']}{i}]")
        labels.append((c["kind"], f"{c['kind']}{i}"))
    nars = [l for k, l in labels if k == "nar"]
    anss = [l for k, l in labels if k == "ans"]

    def mix(ls, out):
        fl.append("".join(f"[{l}]" for l in ls) + f"amix=inputs={len(ls)}:normalize=0:dropout_transition=0,apad[{out}]")

    if nars:
        mix(nars, "nb")
    if anss:
        mix(anss, "ab")
    if nars and anss:
        fl.append("[nb]asplit[nb1][nb2];[ab][nb2]sidechaincompress=threshold=0.02:ratio=6[ad];[nb1][ad]amix=inputs=2:normalize=0[aout]")
    else:
        fl.append("[nb]anull[aout]")
    vf = (f"[0:v]scale=1280:720:flags=lanczos,pad=1280:860:0:0:color={PAD},"
          f"subtitles={srt}:force_style='FontName=DejaVu Sans,FontSize=9,MarginV=18,Alignment=2,PrimaryColour=&H202020&,"
          f"OutlineColour=&Hfff8ec&,BorderStyle=1,Outline=0,WrapStyle=0'[v]")
    out = f"{W}/part_{part}.mp4"
    run("ffmpeg", "-y", *vin, *ins, "-filter_complex", ";".join([vf] + fl), "-map", "[v]", "-map", "[aout]",
        "-t", f"{length:.2f}", "-r", 25, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", 23, "-c:a", "aac", "-b:a", "128k", out)
    return out


parts = []
for key, page in (("P0", 2), ("P1", 7), ("P2", 9), ("P3", 14)):
    png = f"{W}/slide{page}"
    run("pdftoppm", "-r", 96, "-png", "-f", page, "-l", page, "-singlefile", PDF, png)
    parts.append((key, [(key, [{"kind": "nar", "name": key, "t": 0.6}], dur(f"{W}/nar/{key}.mp3") + 1.4, png + ".png")]))
order = {"P0": parts[0]}
for part in "AB":
    j = json.load(open(f"{W}/cues_{part}.json"))
    vid = max(glob.glob(f"{W}/raw_{part}/*.webm"), key=os.path.getmtime)
    order[part] = (part, [(part, j["cues"], j["end"] + 0.6, vid)])
order.update({p[0]: p for p in parts[1:]})
files = []
for k in ("P0", "A", "B", "P1", "P2", "P3"):
    part, [(name, cues, length, src)] = order[k]
    files.append(build(name, src, cues, length, still=src if src.endswith(".png") else None))
lst = f"{W}/parts.txt"
open(lst, "w").write("".join(f"file '{f}'\n" for f in files))
run("ffmpeg", "-y", "-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", OUT)
print(OUT, round(dur(OUT), 1), "s")
