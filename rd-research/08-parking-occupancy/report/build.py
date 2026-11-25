"""
Zostaví report z výsledkov v ../vysledky/:
  template.html -> navrh_08_obsadenost_parkovisk.html (+ .pdf)
  kapitola 8     -> navrh_08_doplnok_pklot.html       (+ .pdf, samostatný doplnok)

python build.py          # len HTML
python build.py --pdf    # aj PDF (potrebuje Google Chrome alebo Chromium)
"""
import argparse
import csv
import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).parent
PROTO = HERE.parent / "prototyp"
RES = HERE.parent / "vysledky"
MAIN = "navrh_08_obsadenost_parkovisk"
ADDENDUM = "navrh_08_doplnok_pklot"
CHROME = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
          "google-chrome", "chromium", "chromium-browser"]


def chart(rows, series, ymin, ymax, bands=(), xlabel=" s", W=700, H=290):
    """Jednoduchý schodovitý graf v SVG (počet áut v čase)."""
    L, R, T, B = 46, 16, 18, 40
    pw, ph = W - L - R, H - T - B
    tmax = max(float(r["t"]) for r in rows)
    x = lambda t: L + pw * t / tmax  # noqa: E731
    y = lambda v: T + ph * (1 - (v - ymin) / (ymax - ymin))  # noqa: E731

    def path(key):
        pts, prev = [], None
        for r in rows:
            t, v = float(r["t"]), int(r[key])
            if prev is not None and v != prev:
                pts.append(f"L{x(t):.1f},{y(prev):.1f}")
            pts.append(("M" if not pts else "L") + f"{x(t):.1f},{y(v):.1f}")
            prev = v
        return " ".join(pts)

    s = [f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
    for a, b, lab in bands:
        s.append(f'<rect x="{x(a):.1f}" y="{T}" width="{x(b)-x(a):.1f}" height="{ph}" fill="#fde68a" opacity=".35"/>')
        s.append(f'<text x="{(x(a)+x(b))/2:.1f}" y="{T+12}" font-size="10" text-anchor="middle" fill="#92400e">{lab}</text>')
    for v in range(ymin, ymax + 1):
        if (ymax - ymin) > 8 and v % 2:
            continue
        s.append(f'<line x1="{L}" x2="{W-R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#e5e7eb"/>')
        s.append(f'<text x="{L-8}" y="{y(v)+4:.1f}" font-size="11" text-anchor="end" fill="#6b7280">{v}</text>')
    t = 0
    while t <= tmax + 0.1:
        s.append(f'<text x="{x(t):.1f}" y="{H-B+16}" font-size="11" text-anchor="middle" fill="#6b7280">{t:.0f}{xlabel}</text>')
        t += 25
    s.append(f'<text x="12" y="{T+ph/2}" font-size="11" fill="#6b7280" transform="rotate(-90 12 {T+ph/2})" '
             f'text-anchor="middle">počet áut</text>')
    for key, _, col, sw, dash in series:
        s.append(f'<path d="{path(key)}" fill="none" stroke="{col}" stroke-width="{sw}" '
                 f'stroke-dasharray="{dash}" stroke-linejoin="round"/>')
    s.append("</svg>")
    legend = "".join(
        f'<span class="lg"><i style="background:{c};{"height:0;border-top:2px dashed "+c if d else ""}"></i>{n}</span>'
        for _, n, c, _, d in series)
    return "\n".join(s) + f'<div class="legend">{legend}</div>'


def fmt(v, pct=True):
    return f"{v*100:.1f} %".replace(".", ",") if pct else f"{v:.2f}".replace(".", ",")


def simulation():
    out = RES / "simulacia" / "series.csv"
    subprocess.run([sys.executable, str(PROTO / "simulate.py"), "--out", str(out)],
                   check=True, capture_output=True, cwd=PROTO)
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    series = [
        ("naive", "Bez pamäte (len čo YOLO vidí práve teraz)", "#c9cdd4", 1.4, ""),
        ("memory", "Parkovisko bez čiar (zóna + pamäť)", "#e8a33d", 2, ""),
        ("slots", "Parkovisko s miestami (navrhované)", "#2563eb", 2.4, ""),
        ("gt", "Skutočný počet áut", "#111827", 1.6, "5 4"),
    ]
    svg = chart(rows, series, 0, 4, [(30, 45, "auto prechádza"), (140, 150, "autobus zakryje miesta")])
    scored = [r for r in rows if float(r["t"]) >= 10]

    def share(k, tol):
        return sum(abs(int(r[k]) - int(r["gt"])) <= tol for r in scored) / len(scored)

    table = "".join(
        f"<tr><td>{n}</td><td>{sum(abs(int(r[k]) - int(r['gt'])) for r in scored) / len(scored):.2f}</td>"
        f"<td>{share(k, 0):.0%}</td><td>{share(k, 1):.0%}</td></tr>"
        for k, n, *_ in series if k != "gt")
    return svg, table


def real_video():
    rows = list(csv.DictReader(open(RES / "video_960px_t30" / "series.csv", encoding="utf-8")))
    rows = [r for r in rows if float(r["t"]) >= 10]  # prvých 10 s sa pamäť napĺňa
    series = [
        ("naive", "Bez pamäte", "#9ca3af", 1.4, ""),
        ("memory", "S pamäťou (navrhované)", "#2563eb", 2.4, ""),
        ("gt", "Skutočný počet áut", "#111827", 1.6, "5 4"),
    ]
    svg = chart(rows, series, 30, 42, [(62, 66, "strih"), (64, 94, "auto na S37"), (104, 118, "pickup prechádza")])

    table = []
    for folder, res, toff in [("video_640px_t30", "640 px", "30 s"), ("video_960px_t30", "960 px", "30 s"),
                              ("video_960px_t15", "960 px", "15 s"), ("video_960px_t60", "960 px", "60 s")]:
        m = json.load(open(RES / folder / "metrics.json", encoding="utf-8"))
        for key, lab in (("bez_pamate", "bez pamäte"), ("s_pamatou", "s pamäťou")):
            if key == "bez_pamate" and toff != "30 s":
                continue  # bez pamäte nezávisí od času uvoľnenia
            d = m[key]
            hl = ' class="hl"' if (folder == "video_960px_t15" and key == "s_pamatou") else ""
            lab += f", uvoľnenie po {toff}" if key == "s_pamatou" else ""
            table.append(
                f"<tr{hl}><td>{res}</td><td>{lab}</td><td>{fmt(d['presnost_miest'])}</td>"
                f"<td>{fmt(d['mae_pocet'], False)}</td><td>{fmt(d['chyba_max_1'])}</td>"
                f"<td>{d['min_pocet']}–{d['max_pocet']}</td><td>{d['zmeny_stavu_miest']}</td></tr>")
    return svg, "".join(table)


def addendum(html):
    """Samostatný doplnok: len kapitola 8 (PKLot), bez odkazov na ostatné kapitoly."""
    head = html[:html.index("<body>") + len("<body>")]
    start = html.index("<!-- ============================== 8. PKLOT")
    sec = html[start:html.index("<!-- ==============================", start + 10)]
    for a, b in [
        ('<section class="page-break">', "<section>"),
        ("<h2>8. Test na celom dni (dataset PKLot)</h2>",
         '<div class="kicker" style="color:#6b7280;font-size:10pt">FlowSight · Úloha 08 · Doplnok k návrhu</div>\n'
         "<h2>Test na celom dni (dataset PKLot)</h2>"),
        ("Video v kapitole 7 je krátke.", "Video z prvého testu bolo krátke (2,5 min)."),
        ("treba spracovať súvislé video (kapitola 7).",
         "treba spracovať súvislé video (ako pri prvom teste, kde pamäť zlepšila presnosť z 95,6 % na 98,3 %)."),
        ("Obr. 11 –", "Obr. 1 –"), ("Obr. 12 –", "Obr. 2 –"),
    ]:
        assert a in sec, a
        sec = sec.replace(a, b, 1)
    sec += """<h3>Ako to spustiť</h3>
<pre>python pklot_download.py --source ufpr05 --date 2013-02-22
python pklot_eval.py --day ../data/pklot/ufpr05_2013-02-22 --model ../../../models/yolov8n.pt \\
       --imgsz 1280 --fp-ratio 1.0 --out ../vysledky/pklot_cely_box</pre>
<p class="src">Zdroj dát: de Almeida a kol., PKLot – dataset parkovísk, 2015.
Použitá verzia: huggingface.co/datasets/Voxel51/PKLot.</p>
"""
    return head + "\n" + sec + "\n</body>\n</html>\n"


def to_pdf(name):
    chrome = next((c for c in CHROME if shutil.which(c) or pathlib.Path(c).exists()), None)
    if chrome is None:
        sys.exit("Chrome/Chromium som nenašiel. HTML otvor v prehliadači a ulož ako PDF.")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={HERE / (name + '.pdf')}", (HERE / (name + ".html")).as_uri()],
                   check=True, capture_output=True)
    print(f"{name}.pdf")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", action="store_true", help="vytvor aj PDF")
    a = ap.parse_args()

    sim_svg, sim_table = simulation()
    real_svg, real_table = real_video()
    html = (HERE / "template.html").read_text(encoding="utf-8")
    html = (html.replace("{{SIM_CHART}}", sim_svg).replace("{{SIM_TABLE}}", sim_table)
                .replace("{{REAL_CHART}}", real_svg).replace("{{REAL_TABLE}}", real_table))
    (HERE / f"{MAIN}.html").write_text(html, encoding="utf-8")
    (HERE / f"{ADDENDUM}.html").write_text(addendum(html), encoding="utf-8")
    print(f"{MAIN}.html, {ADDENDUM}.html")
    if a.pdf:
        to_pdf(MAIN)
        to_pdf(ADDENDUM)


if __name__ == "__main__":
    main()
