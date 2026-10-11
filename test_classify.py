import json
from pathlib import Path

def classify_circuit(components):
    active = [c for c in components if c.get("cls_name") not in ("text", "junction", "crossover") and "gnd" not in c.get("cls_name", "")]
    if not active:
        return "empty"
    
    xs = [(c["bbox"][0] + c["bbox"][2]) / 2 for c in active]
    ys = [(c["bbox"][1] + c["bbox"][3]) / 2 for c in active]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(1.0, max_x - min_x)
    span_y = max(1.0, max_y - min_y)

    # Find sources
    sources = [c for c in active if any(k in c["cls_name"].lower() for k in ("voltage", "battery", "source"))]
    
    # Check if there is a vertical source on the left perimeter
    has_left_source = False
    for s in sources:
        s_cx = (s["bbox"][0] + s["bbox"][2]) / 2
        s_cy = (s["bbox"][1] + s["bbox"][3]) / 2
        # Near left border
        if s_cx - min_x < 0.25 * span_x:
            # Check if passives are located significantly to the right
            passives = [c for c in active if c not in sources]
            if passives and min((p["bbox"][0] + p["bbox"][2])/2 for p in passives) > s_cx + 0.15 * span_x:
                has_left_source = True
                break

    # Cluster by Y into horizontal rows
    sorted_by_y = sorted(active, key=lambda c: (c["bbox"][1] + c["bbox"][3])/2)
    rows = []
    for c in sorted_by_y:
        cy = (c["bbox"][1] + c["bbox"][3]) / 2
        placed = False
        for r in rows:
            mean_y = sum((x["bbox"][1] + x["bbox"][3])/2 for x in r) / len(r)
            if abs(cy - mean_y) < 75.0:
                r.append(c)
                placed = True
                break
        if not placed:
            rows.append([c])

    # A parallel ladder requires 2+ rows where each row has passives/branches spanning across X
    # And there is NOT a left perimeter source that feeds a top rail
    if len(rows) >= 2 and not has_left_source:
        # Check if rows have similar horizontal extents
        all_multicomponent_or_spanning = True
        for r in rows:
            r_xs = [(c["bbox"][0] + c["bbox"][2])/2 for c in r]
            if len(r) == 1 and (max(r_xs) - min(r_xs)) < 0.2 * span_x:
                all_multicomponent_or_spanning = False
        if all_multicomponent_or_spanning or len(rows) >= 3:
            return "parallel_ladder"

    return "single_loop"

# Test on cir1
with open("outputs/run1/final_result/json/cir1.final.json") as f:
    cir1_data = json.load(f)
print("cir1 classification:", classify_circuit(cir1_data["components"]))

# Test on LED circuit
jobs = sorted(Path("outputs/ui_jobs").glob("*"), key=lambda p: p.stat().st_mtime)
latest = jobs[-1]
with open(latest / "circuit.json") as f:
    led_data = json.load(f)

# Use cleaned components
from test_fix_hallucination import suppress_duplicates
cleaned_led = suppress_duplicates(led_data["components"])
print("LED circuit classification:", classify_circuit(cleaned_led))
