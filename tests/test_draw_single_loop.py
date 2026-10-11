import schemdraw
import schemdraw.elements as elm

def test_draw_single_loop():
    with schemdraw.Drawing(file="scratch_single_loop.png", show=False) as d:
        d.config(fontsize=12, unit=3.0)

        # Left: Battery V1 5V going up
        d += elm.Battery().up().label("5V", loc="left")

        # Top: R1 220Ω and LED1
        d += elm.Resistor().right().label("R1\n220Ω")
        d += elm.LED().right().label("LED1")

        # Right side wire down
        d += elm.Line().down()

        # Bottom return rail to left
        d += elm.Line().left().tox(4.0)
        d += elm.Dot()
        d.push()
        d += elm.Ground().down()
        d.pop()
        d += elm.Line().left().tox(0)

    print("Success drawing single loop!")

if __name__ == "__main__":
    test_draw_single_loop()
