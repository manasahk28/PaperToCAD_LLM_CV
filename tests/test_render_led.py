import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import schemdraw
import schemdraw.elements as elm

def test_schemdraw_single_loop_from_components():
    jobs = sorted((REPO_ROOT / "outputs" / "ui_jobs").glob("*"), key=lambda p: p.stat().st_mtime)
    latest = jobs[-1]
    with open(latest / "circuit.json", encoding="utf-8") as f:
        d = json.load(f)

    from test_fix_hallucination import suppress_duplicates, bind_text_labels
    text_boxes = [c for c in d["components"] if c["cls_name"] == "text"]
    cleaned = suppress_duplicates(d["components"])
    bind_text_labels(cleaned, text_boxes)

    gnd_comp = next((c for c in cleaned if "gnd" in c["cls_name"]), None)
    active = [c for c in cleaned if c != gnd_comp]

    sources = [c for c in active if any(k in c["cls_name"] for k in ("voltage", "battery", "source"))]
    passives = [c for c in active if c not in sources]
    passives.sort(key=lambda c: (c["bbox"][0] + c["bbox"][2]) / 2)

    out_preview = REPO_ROOT / "outputs" / "test_previews" / "scratch_led_reconstructed.png"
    with schemdraw.Drawing(file=str(out_preview), show=False) as d_draw:
        d_draw.config(fontsize=12, unit=2.8)

        # Source on left
        src = sources[0] if sources else None
        s_val = src.get("value") or "5V" if src else "Vin"
        s_desig = src.get("designator") or "V1" if src else "V1"
        lbl = f"{s_desig}\n{s_val}" if s_val else s_desig

        if src and "battery" in src["cls_name"]:
            d_draw += elm.Battery().up().label(lbl, loc="left")
        else:
            d_draw += elm.SourceV().up().label(lbl, loc="left")

        # Top passives in series
        for p in passives:
            p_cls = p["cls_name"].lower()
            p_lbl = p.get("text_label") or p_cls
            if "light_emitting" in p_cls or "led" in p_lbl.lower():
                d_draw += elm.LED().right().label(p_lbl)
            elif "diode" in p_cls:
                d_draw += elm.Diode().right().label(p_lbl)
            elif "resistor" in p_cls:
                d_draw += elm.Resistor().right().label(p_lbl)
            elif "capacitor" in p_cls:
                d_draw += elm.Capacitor().right().label(p_lbl)
            elif "inductor" in p_cls:
                d_draw += elm.Inductor().right().label(p_lbl)
            else:
                d_draw += elm.Resistor().right().label(p_lbl)

        # Right side wire down
        d_draw += elm.Line().down()

        # Bottom return rail to left with ground
        d_draw += elm.Line().left().tox(3.5)
        if gnd_comp:
            d_draw += elm.Dot()
            d_draw.push()
            d_draw += elm.Ground().down()
            d_draw.pop()
        d_draw += elm.Line().left().tox(0)

    print("Generated scratch_led_reconstructed.png successfully!")

if __name__ == "__main__":
    test_schemdraw_single_loop_from_components()
