import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_fix_hallucination import suppress_duplicates, bind_text_labels

def test_spice_synthesis():
    jobs = sorted((REPO_ROOT / "outputs" / "ui_jobs").glob("*"), key=lambda p: p.stat().st_mtime)
    latest = jobs[-1]
    with open(latest / "circuit.json", encoding="utf-8") as f:
        d = json.load(f)

    text_boxes = [c for c in d["components"] if c["cls_name"] == "text"]
    cleaned = suppress_duplicates(d["components"])
    bind_text_labels(cleaned, text_boxes)

    # Detect topology
    from test_classify import classify_circuit
    topo = classify_circuit(cleaned)
    print("Classified topology:", topo)

    gnd_comp = next((c for c in cleaned if "gnd" in c["cls_name"]), None)
    active = [c for c in cleaned if c != gnd_comp]

    sources = [c for c in active if any(k in c["cls_name"] for k in ("voltage", "battery", "source"))]
    passives = [c for c in active if c not in sources]
    passives.sort(key=lambda c: (c["bbox"][0] + c["bbox"][2]) / 2)

    lines = [
        "* ==================================================",
        f"* SPICE Netlist - Reconstructed from Hand-Drawn Schematic",
        f"* Target: {d['image_name']}",
        "* ==================================================",
        f".TITLE {d['image_name']}",
        ".OPTIONS ABSTOL=1n RELTOL=1e-3",
        ""
    ]

    if topo == "single_loop" and sources:
        src = sources[0]
        s_desig = src.get("designator") or "V1"
        s_val = src.get("value") or "5V"
        # DC voltage source from N1 to 0
        lines.append(f"{s_desig} N1 0 DC {s_val}")
        
        curr_node = 1
        for i, p in enumerate(passives):
            p_cls = p["cls_name"].lower()
            p_desig = p.get("designator") or f"R{i+1}"
            p_val = p.get("value") or "1k"
            
            in_node = f"N{curr_node}"
            if i == len(passives) - 1:
                out_node = "0"
            else:
                curr_node += 1
                out_node = f"N{curr_node}"

            if "resistor" in p_cls:
                lines.append(f"{p_desig} {in_node} {out_node} {p_val}")
            elif "light_emitting" in p_cls or "led" in p_cls:
                lines.append(f"{p_desig} {in_node} {out_node} DLED_AUTO")
            elif "diode" in p_cls:
                lines.append(f"{p_desig} {in_node} {out_node} D1N4148")
            elif "capacitor" in p_cls:
                lines.append(f"{p_desig} {in_node} {out_node} {p_val}")
            elif "inductor" in p_cls:
                lines.append(f"{p_desig} {in_node} {out_node} {p_val}")
            else:
                lines.append(f"{p_desig} {in_node} {out_node} {p_val}")

    lines.extend([
        "",
        "* ---- Device Models ----",
        ".MODEL DLED_AUTO D (IS=1e-18 N=2 RS=5)",
        ".MODEL D1N4148 D (IS=2.52n RS=0.568 N=1.752)",
        "",
        "* ---- Analysis Directive ----",
        ".OP",
        ".END"
    ])

    spice_text = "\n".join(lines)
    print("\nSynthesized Netlist:\n" + spice_text)

if __name__ == "__main__":
    test_spice_synthesis()
