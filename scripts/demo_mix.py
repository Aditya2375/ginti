"""Mix the recorded screen, narration and answer clips into the demo MP4.
Usage: python scripts/demo_mix.py WORKDIR OUT.mp4     (needs ffmpeg with libass)
Inputs come from demo_record.py: WORKDIR/raw/*.webm, cues.json, nar/*.mp3 and durations.json, hi/*.wav."""

import glob
import json
import subprocess
import sys
import textwrap

W, OUT = sys.argv[1], sys.argv[2]
c = json.load(open(f"{W}/cues.json"))
D = json.load(open(f"{W}/nar/durations.json"))
raw = glob.glob(f"{W}/raw/*.webm")[0]
vd = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", raw]))
cues = c["cues"]
n8t = vd + 0.5
cues.append({"kind": "nar", "name": "N8", "t": n8t, "caption": "Limits: 99% on 508 synthetic clips in every answer range the app uses. Not tested on real children or phones. One command: docker compose up. MIT licence."})
total = n8t + D["N8"] + 1.5


def ts(x):
    return f"{int(x // 3600):02d}:{int(x % 3600 // 60):02d}:{x % 60:06.3f}".replace(".", ",")


with open(f"{W}/subs.srt", "w") as f:
    i = 1
    for q in cues:
        if q["kind"] == "nar":
            f.write(f"{i}\n{ts(q['t'])} --> {ts(q['t'] + D[q['name']])}\n" + "\n".join(textwrap.wrap(q["caption"], 70)) + "\n\n")
            i += 1
inputs, fl, nars, anss = ["-i", raw], [], [], []
for k, q in enumerate(cues, 1):
    inputs += ["-i", f"{W}/nar/{q['name']}.mp3" if q["kind"] == "nar" else f"{W}/hi/{q['name']}.wav"]
    fl.append(f"[{k}:a]aresample=44100,aformat=channel_layouts=mono,adelay={int(q['t'] * 1000)}:all=1[a{k}]")
    (nars if q["kind"] == "nar" else anss).append(f"[a{k}]")
fl += ["".join(nars) + f"amix=inputs={len(nars)}:normalize=0[nar]",
       "".join(anss) + f"amix=inputs={len(anss)}:normalize=0,volume=1.6,asplit[ans][sc]",
       "[nar][sc]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=300[nd]",
       f"[nd][ans]amix=inputs=2:normalize=0,apad,atrim=0:{total:.2f}[aout]",
       f"[0:v]tpad=stop_mode=clone:stop_duration={total - vd + 1:.2f},"
       f"subtitles={W}/subs.srt:force_style='FontSize=9,Outline=1,Shadow=0,MarginV=8',trim=0:{total:.2f},setpts=PTS-STARTPTS,fps=25,format=yuv420p[vout]"]
cmd = ["ffmpeg", "-y", *inputs, "-filter_complex", ";".join(fl), "-map", "[vout]", "-map", "[aout]", "-c:v", "libx264", "-crf", "24",
       "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", OUT]
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.returncode, "total seconds", round(total, 1))
if r.returncode:
    print(r.stderr[-800:])
