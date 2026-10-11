import sys
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import json
import math
import re
from pathlib import Path

def compute_iou(b1, b2):
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    a1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
    a2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
    union = a1 + a2 - inter
    iou = inter / union if union > 0 else 0
    iom = inter / min(a1, a2) if min(a1, a2) > 0 else 0
    return iou, iom

def suppress_duplicates(components):
    """Cross-class NMS to remove duplicate/overlapping detections."""
    non_text = [c for c in components if c["cls_name"] != "text"]
    # Sort by confidence descending
    non_text.sort(key=lambda c: c["confidence"], reverse=True)
    
    keep = []
    for c in non_text:
        suppressed = False
        b1 = c["bbox"]
        for k in keep:
            b2 = k["bbox"]
            iou, iom = compute_iou(b1, b2)
            # If high overlap or one largely contained inside the other
            if iou > 0.35 or iom > 0.55:
                # Prefer more specific sub-class (e.g. diode.light_emitting > diode)
                if "light_emitting" in c["cls_name"] and "light_emitting" not in k["cls_name"]:
                    keep.remove(k)
                    break
                suppressed = True
                break
        if not suppressed:
            keep.append(c)
    return keep

def bind_text_labels(components, text_boxes):
    """Smartly binds designator and value to each component."""
    for c in components:
        cb = c["bbox"]
        c_cx = (cb[0] + cb[2]) / 2.0
        c_cy = (cb[1] + cb[3]) / 2.0
        
        # Find all nearby text boxes
        nearby = []
        for tb in text_boxes:
            tbb = tb["bbox"]
            t_cx = (tbb[0] + tbb[2]) / 2.0
            t_cy = (tbb[1] + tbb[3]) / 2.0
            dist = math.hypot(c_cx - t_cx, c_cy - t_cy)
            if dist < 220:
                nearby.append((dist, tb["text_label"]))
        
        nearby.sort(key=lambda x: x[0])
        desig = ""
        val = ""
        
        for dist, text in nearby:
            text = text.strip()
            if not text:
                continue
            # Check if value (has digits and electrical unit or ohm)
            if any(u in text for u in ["Ω", "k", "m", "u", "p", "n", "V", "v", "A", "a", "H", "h", "F", "f"]) and any(c.isdigit() for c in text):
                if not val:
                    val = text
            elif re.match(r"^[A-Za-z]+[0-9]*$", text):
                if not desig:
                    desig = text
            else:
                if not val:
                    val = text

        c["designator"] = desig
        c["value"] = val
        if desig and val:
            c["text_label"] = f"{desig}\n{val}"
        elif desig:
            c["text_label"] = desig
        elif val:
            c["text_label"] = val

def test():
    jobs = sorted(Path("outputs/ui_jobs").glob("*"), key=lambda p: p.stat().st_mtime)
    latest = jobs[-1]
    with open(latest / "circuit.json", encoding="utf-8") as f:
        d = json.load(f)
    
    text_boxes = [c for c in d["components"] if c["cls_name"] == "text"]
    cleaned = suppress_duplicates(d["components"])
    bind_text_labels(cleaned, text_boxes)
    
    print(f"Cleaned components ({len(cleaned)} total):")
    for c in cleaned:
        print(f" - {c['cls_name']:<22} conf={c['confidence']} bbox={c['bbox']} label={repr(c.get('text_label'))}")

if __name__ == "__main__":
    test()
