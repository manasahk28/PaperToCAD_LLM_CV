import schemdraw
import schemdraw.elements as elm

def test_draw_cir1_v2():
    with schemdraw.Drawing(file="scratch_cir1_v2.png", show=False) as d:
        d.config(fontsize=12, unit=2.5)

        branches = [
            [
                ("inductor", "1H"),
                ("capacitor", "1F"),
                ("resistor", "10kΩ")
            ],
            [
                ("resistor", "10Ω"),
                ("source_i", "2A")
            ],
            [
                ("inductor", "100mH"),
                ("resistor", "100Ω")
            ]
        ]

        y_spacing = 3.0
        # Target total width of each branch
        max_comps = max(len(b) for b in branches)
        # Each comp is unit 2.5 length, plus spacing
        total_width = (max_comps * 2.5) + 1.0

        for idx, branch in enumerate(branches):
            y = -idx * y_spacing
            # Start branch at (0, y)
            d += elm.Dot().at((0, y))
            
            # Draw components in branch
            curr_pos = (0, y)
            comp_width = total_width / len(branch)
            
            for c_type, label in branch:
                if c_type == "inductor":
                    elem = elm.Inductor().right().label(label).length(comp_width)
                elif c_type == "capacitor":
                    elem = elm.Capacitor().right().label(label).length(comp_width)
                elif c_type == "resistor":
                    elem = elm.Resistor().right().label(label).length(comp_width)
                elif c_type == "source_i":
                    elem = elm.SourceI().right().label(label).length(comp_width)
                elif c_type == "source_v":
                    elem = elm.SourceV().right().label(label).length(comp_width)
                else:
                    elem = elm.Resistor().right().label(label).length(comp_width)
                d += elem
            
            # Ensure branch reaches total_width
            d += elm.Line().right().tox(total_width)
            d += elm.Dot().at((total_width, y))

        # Left vertical rail
        y_top = 0
        y_bottom = -(len(branches) - 1) * y_spacing
        d += elm.Line().at((0, y_top)).to((0, y_bottom))
        
        # Ground at left rail (middle or bottom)
        y_gnd = -(len(branches) - 1) * y_spacing / 2.0
        d += elm.Ground().at((0, y_gnd)).left()

        # Right vertical rail
        d += elm.Line().at((total_width, y_top)).to((total_width, y_bottom))

    print("Success drawing cir1 v2!")

if __name__ == "__main__":
    test_draw_cir1_v2()
