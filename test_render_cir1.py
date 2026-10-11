import schemdraw
import schemdraw.elements as elm

def test_draw_cir1():
    with schemdraw.Drawing(file="scratch_cir1.png", show=False) as d:
        d.config(fontsize=12, unit=2.5)

        # Branch 1 (top)
        top_start = d.add(elm.Dot())
        d += elm.Inductor().right().label("1H")
        d += elm.Capacitor().right().label("1F")
        d += elm.Resistor().right().label("10kΩ")
        top_end = d.add(elm.Dot())

        # Branch 2 (middle)
        d += elm.Line().left().at(top_end.center).down(3)
        mid_end = d.add(elm.Dot())
        d += elm.SourceI().left().label("2A", loc="bottom")
        d += elm.Resistor().left().label("10Ω", loc="bottom")
        mid_start = d.add(elm.Dot())

        # Branch 3 (bottom)
        d += elm.Line().down(3).at(mid_start.center)
        bot_start = d.add(elm.Dot())
        d += elm.Inductor().right().label("100mH", loc="bottom")
        d += elm.Resistor().right().label("100Ω", loc="bottom")
        bot_end = d.add(elm.Dot())

        # Connect left rail
        d += elm.Line().up().at(mid_start.center).to(top_start.center)
        # Connect ground at mid_start or left rail
        d += elm.Ground().at(mid_start.center).left()

        # Connect right rail
        d += elm.Line().up().at(bot_end.center).to(mid_end.center)
        d += elm.Line().up().at(mid_end.center).to(top_end.center)

    print("Success drawing cir1!")

if __name__ == "__main__":
    test_draw_cir1()
