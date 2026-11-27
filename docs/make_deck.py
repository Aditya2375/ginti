"""Build the Round 2 idea deck as a text PDF.  Usage: python docs/make_deck.py OUT.pdf

Everything in the deck about the product is something the code and tests in this repo do.
Numbers come from README.md (benchmark) and from the sources listed on the last slide.
"""

import os
import sys

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Frame, KeepInFrame, Paragraph, Spacer, Table, TableStyle

pdfmetrics.registerFont(TTFont("Body", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
W, H = 960, 540
GREEN, INK, MUTED, CREAM = colors.HexColor("#0b5d4b"), colors.HexColor("#1d1a16"), colors.HexColor("#5d554a"), colors.HexColor("#fff8ec")

body = ParagraphStyle("b", fontName="Body", fontSize=19, leading=26, textColor=INK, spaceAfter=9)
small = ParagraphStyle("s", parent=body, fontSize=15, leading=20, spaceAfter=5)
cell = ParagraphStyle("c", parent=body, fontSize=14.5, leading=19, spaceAfter=0)
cellb = ParagraphStyle("cb", parent=cell, fontName="Bold")

SLIDES = []


def slide(title, items=None, table=None, widths=None, note=None, size=None, extra=None):
    SLIDES.append(dict(title=title, items=items or [], table=table, widths=widths, note=note, size=size, extra=extra))


slide("Ginti: maths you answer out loud",
      ["Round 2 entry, theme: Inclusive education. Solo entry by Aditya Kulkarni.",
       "A child hears a sum, says the answer in Hindi or English, and hears whether it was right. Answers are spoken, not typed. No password, no account, no API keys.",
       "Runs with one command: <b>docker compose up</b>. Code: github.com/Aditya2375/ginti (MIT)."], size=24)

slide("The problem",
      ["Many children in India are behind in basic arithmetic. In the rural ASER 2024 survey, 33.7% of Std III children could do at least a subtraction, and 30.7% of Std V children could do a division.",
       "Practice that happens on a screen usually asks for reading and typing. For a child who is still learning to read Devanagari or English, or who has never typed on a keyboard, the interface gets in the way before the maths does.",
       "Speaking is the one skill almost every child already has in their own language.",
       "<font color='#5d554a'>Our assumption, not a finding: for young children, answering aloud lowers the barrier to daily practice. We have not tested this with children.</font>"])

slide("Who it is for",
      ["<b>Children</b> in primary classes who can say a number answer but are slow to type it.",
       "<b>Teachers</b> who want to see, per child, which facts keep going wrong (for example 7 x 8) instead of a single score.",
       "<b>Schools and NGOs</b> with one shared laptop or a few cheap phones and no budget for per-user software.",
       "What they need from the product: it works offline on a local network, costs nothing per child, and does not collect personal data."])

slide("What a child does",
      ["1. Picks a name, a language (Hindi or English) and a topic: add, subtract, tables, or a mix.",
       "2. Sees the sum large on screen and hears it read aloud.",
       "3. Taps the microphone and says the answer, for example <b>pachpan</b> or <b>fifty five</b>.",
       "4. Sees what the app heard for 2.5 seconds, and can say <b>no, say it again</b> if it misheard.",
       "5. Gets spoken feedback. Missed facts come back soon, known facts come back later. Five right in a row moves up a level.",
       "Spoken commands: <b>dobara / repeat</b> and <b>chhodo / skip</b>."], size=21)

slide("What is built today (all of it is in the repo and tested)",
      table=[["Part", "What it does"],
             ["Speech", "Offline recognition of numbers in Hindi and Indian English, limited per question to the words an answer could use"],
             ["Numbers", "Hindi 0 to 99 as written out words, hundreds and thousands, Roman Hindi typing, English; round trip tested for all 0 to 9,999"],
             ["Practice", "Add, subtract, times tables; four levels; spaced repetition per fact; spoken prompts in both languages"],
             ["Teacher page", "PIN protected: recent accuracy, median time on right answers, level per topic, most missed facts, CSV export, delete a learner"],
             ["Data", "SQLite on a Docker volume. Nickname, answers and timings only. No audio is kept"],
             ["Run", "docker compose up. No .env and no keys needed. Continuous integration builds it and runs a smoke test"]],
      widths=[150, 730])

slide("How it works",
      ["Browser: captures the microphone, converts it to 16 kHz mono audio and streams it over a WebSocket.",
       "Server (Python, FastAPI): decodes the audio with Vosk, an open-source offline recogniser, using its small Hindi and Indian-English models.",
       "For each question the recogniser is restricted to the words needed for plausible answers plus two commands. For 3 + 4 the answer can only be a number up to 20, so a similar-sounding word like <b>saath</b> (60) cannot replace <b>saat</b> (7).",
       "A parser turns the words into a number. Unclean input, like \"seven eight\", counts as not heard. The recogniser can still mishear a clean word as another valid number, so the child sees what was heard first.",
       "The server holds the correct answer and does the scoring, so the browser cannot mark itself right."], size=20)
slide("Pipeline", extra="pipeline")
slide("What it looks like", extra="screens")

slide("Evidence so far",
      table=[["Check", "Result"],
             ["508 synthetic clips (two voices per language), each decoded in every answer band the app can assign: 1,208 results", "1,197 correct (99.1%). Hindi 0 to 99: 532/536, Hindi 100 to 999: 52/56. English 0 to 99: 533/536, 100 to 999: 56/56. Known miss: Hindi 7 heard as 60 in wide bands"],
             ["Stress, 33 fixture clips (80 results)", "Clean 77, pitch +40%: 65, noise 10 dB: 73, noise 0 dB: 56. Synthetic, crude"],
             ["Speed", "One run, one decoding process: 1,208 decodes, 2,337 s of audio in 33.7 s, about 69 times faster than real time"],
             ["Automated tests", "86 tests: numbers, question engine, database, every API route and its bad-input cases, fixture audio"],
             ["Browser run", "One 10-question round in Chrome with recorded clips played into the microphone path: 10 of 10 scored right"],
             ["Docker", "CI builds the image, starts it with docker compose up, and recognises a spoken answer through it"]],
      widths=[320, 560])
SLIDES[-1]["note"] = "<b>Not yet tested:</b> real children, real phones, a classroom, background noise. The clips above are synthetic or recorded, not live speech from learners."

slide("Market, with the assumptions shown",
      ["India's school system has 24.8 crore students in 14.72 lakh schools (UDISE+ 2023-24, via the Economic Survey 2024-25).",
       "ASER 2024 (a survey of rural children) found arithmetic is where many are behind: 33.7% of Std III can subtract, 30.7% of Std V can divide.",
       "We do not claim a revenue market. Ginti is free and open source. The addressable group is the children in classes where basic arithmetic is being learned, in schools that can run a laptop or a phone on a local network.",
       "We have no pilots, no customers and no usage numbers yet. Any share we named would be invented."], size=20)

slide("What it depends on, and what could go wrong",
      table=[["Dependency", "Cost", "Risk and what we do about it"],
             ["Vosk and its two small models (Apache 2.0)", "Free", "Small models make mistakes on unfamiliar voices. Mitigation: the per-question word limit, showing what was heard, a redo button, typed fallback. Measured only on synthetic voices"],
             ["Model download host (alphacephei.com)", "Free", "If it is down at build time, the build fails. Models are pinned by SHA-256. A copy can be hosted elsewhere"],
             ["Browser microphone, AudioWorklet", "Free", "Needs localhost or HTTPS. A school network needs a TLS proxy"],
             ["Device text-to-speech voice", "Free", "If a phone has no Hindi voice, the question is shown but not read aloud. Not yet checked on real phones"],
             ["Docker base image, GitHub", "Free", "Standard container risk. No paid API anywhere in the runtime"]],
      widths=[250, 70, 560])

slide("Cost to run",
      ["There is no per-answer fee and no key. The only cost is the machine it runs on.",
       "Measured: one decoding process runs about 69 times faster than real time. The code allows 8 simultaneous microphone sessions per server process.",
       "Not measured: behaviour with 40 children on one server, or on a Raspberry Pi or a low-end phone. Those are the first things to test in a classroom.",
       "Data is a small SQLite file on a Docker volume. There is no backup yet."], size=21)

slide("Launch plan",
      table=[["When", "What", "How we will know"],
             ["Weeks 1 to 2", "Record real children and adults saying numbers (with consent), re-run the benchmark", "Accuracy on real voices, and where it breaks"],
             ["Weeks 2 to 4", "One classroom pilot through a teacher or NGO contact. We have none yet", "Questions answered per child per week, teacher feedback"],
             ["Month 2", "TLS deployment guide, backup, a Hindi hundreds fix (the weakest case today)", "Hindi 100 to 999 accuracy above 98%"],
             ["Month 3", "Add division and simple word problems, more languages the Vosk project has models for", "Which language teachers ask for first"]],
      widths=[120, 470, 290])

slide("Limits we state up front",
      ["Recognition numbers are from synthetic voices. Children will be harder.",
       "Hindi hundreds are the weak spot: the recogniser sometimes drops the word <b>sau</b>.",
       "A nickname is the login. Anyone can practise as someone else's nickname. The teacher page has a PIN.",
       "Whole numbers up to 9,999. Addition, subtraction, multiplication only.",
       "One server process, SQLite, no TLS built in."], size=21)

slide("What Round 3 would add",
      ["Real-voice accuracy work with children's recordings, and per-age tuning of the answer limits.",
       "More question types that fit speech well: counting, number words, simple word problems.",
       "A teacher assignment view: choose the facts a class should practise this week.",
       "A hosted demo for teachers to try before installing."], size=22)

slide("Sources",
      ["ASER 2024 key findings, Ministry of Education (PIB): static.pib.gov.in/WriteReadData/specificdocs/documents/2025/feb/doc202524496701.pdf",
       "ASER 2024 final report: asercentre.org/wp-content/uploads/2022/12/ASER_2024_Final-Report_13_2_24.pdf",
       "Economic Survey 2024-25 on UDISE+ 2023-24 (PIB): pib.gov.in/PressReleaseIframePage.aspx?PRID=2097864",
       "Vosk models and licences: alphacephei.com/vosk/models",
       "Benchmark, tests and source: github.com/Aditya2375/ginti (README.md, scripts/bench_asr.py)"], size=16)


HERE = os.path.dirname(os.path.abspath(__file__))


def pipeline(c):
    steps = [("Child's browser", "microphone, 16 kHz audio, worklet"), ("WebSocket", "audio frames, 15 s limit per socket"),
             ("Vosk (offline)", "grammar for this sum + 2 commands"), ("Number parser", "Hindi, Roman Hindi, English"),
             ("Server scores", "SQLite: attempt, box, level"), ("Spoken feedback", "device voice, teacher page")]
    bw, bh, gap, y = 128, 110, 18, 270
    x = 40
    for i, (a, b) in enumerate(steps):
        c.setFillColor(colors.white); c.setStrokeColor(GREEN); c.setLineWidth(2)
        c.roundRect(x, y, bw, bh, 8, fill=1, stroke=1)
        c.setFillColor(INK); c.setFont("Bold", 13); c.drawCentredString(x + bw / 2, y + bh - 28, a)
        c.setFillColor(MUTED); c.setFont("Body", 10)
        words, line, ly = b.split(), "", y + bh - 52
        for w in words:
            if c.stringWidth(line + " " + w, "Body", 10) > bw - 14:
                c.drawCentredString(x + bw / 2, ly, line.strip()); line, ly = "", ly - 14
            line += " " + w
        c.drawCentredString(x + bw / 2, ly, line.strip())
        if i < len(steps) - 1:
            c.setStrokeColor(GREEN); c.line(x + bw, y + bh / 2, x + bw + gap, y + bh / 2)
            c.line(x + bw + gap - 6, y + bh / 2 + 4, x + bw + gap, y + bh / 2); c.line(x + bw + gap - 6, y + bh / 2 - 4, x + bw + gap, y + bh / 2)
        x += bw + gap
    c.setFillColor(INK); c.setFont("Body", 15)
    c.drawString(40, 215, "No audio is written to disk. No outside service is called at run time.")
    c.drawString(40, 190, "The server alone holds the right answer. The browser sends what was said.")
    c.drawString(40, 165, "Runs as one container: docker compose up. Models are fetched at image build, pinned by SHA-256.")


def screens(c):
    for i, (img, cap) in enumerate([("child.png", "Child screen: the sum, hear again, speak, or type"), ("teacher.png", "Teacher page: per-learner accuracy, time, level")]):
        im = ImageReader(os.path.join(HERE, "img", img))
        iw, ih = im.getSize()
        h = 340.0
        w = h * iw / ih
        x = 40 + i * 450 + (430 - w) / 2 if w < 430 else 40 + i * 450
        c.drawImage(im, x, 130, width=min(w, 430), height=h if w < 430 else 430 * ih / iw)
        c.setFillColor(INK); c.setFont("Body", 13); c.drawString(40 + i * 450, 100, cap)
    c.setFillColor(MUTED); c.setFont("Body", 12)
    c.drawString(40, 60, "Screenshots of the running app in Chrome with test data.")
    c.drawString(40, 44, "The Listening line on the child screen was set by hand: the capture machine has no microphone.")


def draw(c, s, n):
    c.setFillColor(CREAM); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setFillColor(GREEN); c.rect(0, H - 78, W, 78, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont("Bold", 30); c.drawString(40, H - 52, s["title"])
    c.setFillColor(MUTED); c.setFont("Body", 11); c.drawRightString(W - 30, 18, f"Ginti  |  {n}")
    flow = []
    st = ParagraphStyle("x", parent=body, fontSize=s["size"], leading=s["size"] * 1.35) if s["size"] else body
    for it in s["items"]:
        flow.append(Paragraph(it, st))
    if s["table"]:
        rows = [[Paragraph(x, cellb if r == 0 else cell) for x in row] for r, row in enumerate(s["table"])]
        t = Table(rows, colWidths=s["widths"])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e7f3ef")), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9cdb8")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        flow.append(t)
    if s["note"]:
        flow.append(Spacer(1, 14))
        flow.append(Paragraph(s["note"], small))
    if s["extra"] == "pipeline":
        return pipeline(c)
    if s["extra"] == "screens":
        return screens(c)
    f = Frame(40, 40, W - 80, H - 78 - 60, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
    f.addFromList([KeepInFrame(W - 80, H - 78 - 60, flow, mode="error")], c)


def main(out):
    c = canvas.Canvas(out, pagesize=(W, H))
    c.setTitle("Ginti: maths you answer out loud"); c.setAuthor("Aditya Kulkarni")
    for i, s in enumerate(SLIDES, 1):
        draw(c, s, i)
        c.showPage()
    c.save()
    print(len(SLIDES), "slides ->", out)


if __name__ == "__main__":
    main(sys.argv[1])
