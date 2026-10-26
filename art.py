# ============================================================
# art.py  -  STEP 12: time-of-day lighting + pixel-art people
#
#   Lighting uses pyxel.pal(a, b) (palette swap): everything drawn while a
#   tint is active is shifted toward dawn / dusk / night colours.
#   pyxel.pal() with no argument resets it.
#
#   Pyxel default palette
#     0 black  1 navy  2 purple  3 teal  4 brown  5 dark blue  6 light blue
#     7 white  8 red   9 orange 10 yellow 11 lime 12 blue 13 gray 14 pink 15 peach
#
#   People are 5 x 7 pixel sprites (8 rows with a hat), feet at (x, y + 3).
# ============================================================
from data import DAY_TICKS, clock_to_t

# ------------------------------------------------------------
# time of day
# ------------------------------------------------------------
DAWN_END = clock_to_t(7)
DUSK_START = clock_to_t(17)
NIGHT_START = clock_to_t(19)
LATE_START = clock_to_t(22)          # guests are asleep (room lights off)

PHASE_LABEL = {"DAWN": "朝", "DAY": "昼", "DUSK": "夕", "NIGHT": "夜"}

# outdoors (site map)
OUT_TINT = {
    "DAWN":  {11: 3, 12: 14, 7: 15},
    "DAY":   {},
    "DUSK":  {11: 3, 12: 9, 6: 9, 7: 15, 13: 4, 15: 9, 10: 9},
    "NIGHT": {11: 3, 3: 1, 12: 5, 6: 5, 7: 13, 15: 4, 13: 1, 10: 9, 9: 4,
              14: 2, 8: 2, 4: 1, 5: 1, 2: 1},
}
# indoors (floor view): lamps are on, so only a soft cast
IN_TINT = {
    "DAWN":  {7: 15},
    "DAY":   {},
    "DUSK":  {7: 15, 6: 15, 12: 6},
    "NIGHT": {7: 15, 6: 5, 13: 5, 12: 5, 11: 3, 4: 2},
}
# a sleeping guest's room after 22:00 (lights off)
SLEEP_TINT = {7: 1, 6: 1, 15: 1, 13: 1, 12: 1, 10: 5, 14: 2, 4: 1, 2: 1, 9: 4,
              3: 1, 8: 2, 11: 3, 5: 1}


def phase(t):
    if t < DAWN_END:
        return "DAWN"
    if t < DUSK_START:
        return "DAY"
    if t < NIGHT_START:
        return "DUSK"
    return "NIGHT"


def late(t):
    return t >= LATE_START


def set_tint(px, mapping):
    px.pal()
    for a, b in mapping.items():
        px.pal(a, b)


def reset_tint(px):
    px.pal()


def glow(px, x, y, r, col, frame=0):
    """dithered light pool (checkerboard dots)"""
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r and (dx + dy + frame) % 2 == 0:
                px.pset(x + dx, y + dy, col)


def sun_moon(px, x, y, t, frame):
    """8x8 HUD icon"""
    ph = phase(t)
    if ph == "NIGHT":
        px.circ(x + 4, y + 4, 3, 10)
        px.circ(x + 6, y + 3, 3, 0)            # crescent
        if frame % 40 < 20:
            px.pset(x, y + 1, 7)
    else:
        col = {"DAWN": 14, "DAY": 10, "DUSK": 9}[ph]
        px.circ(x + 4, y + 4, 2, col)
        for dx, dy in ((0, -4), (0, 4), (-4, 0), (4, 0)):
            px.pset(x + 4 + dx, y + 4 + dy, col)


# ------------------------------------------------------------
# pixel-art people
# ------------------------------------------------------------
HAIRS = (0, 4, 9, 10, 13, 2, 4, 0)
SHIRTS = (8, 9, 10, 11, 12, 14, 3, 6)


def hair_of(key):
    return HAIRS[key % len(HAIRS)]


def shirt_of(key):
    return SHIRTS[key % len(SHIRTS)]


def person(px, x, y, body, hair=0, skin=15, legs=1, shoes=0, step=0, face=1,
           hat=None, accent=None, dress=False, glasses=False, apron=None):
    """5x7 sprite. (x, y) = centre of the body.  face: 1 right / -1 left
    step: 0 standing, 1/2 walking frames"""
    x, y = int(x), int(y)
    p = px.pset
    # hat
    if hat is not None:
        for dx in (-1, 0, 1):
            p(x + dx, y - 5, hat)
    # hair
    for dx in (-1, 0, 1):
        p(x + dx, y - 4, hair)
    p(x - face, y - 3, hair)
    # face
    p(x, y - 3, skin)
    p(x + face, y - 3, skin)
    if glasses:                          # sunglasses
        p(x + face, y - 3, 0)
        p(x + 2 * face, y - 3, 0)
    # body + arms
    arm = (step == 1)
    for dx in (-1, 0, 1):
        p(x + dx, y - 2, body)
        p(x + dx, y - 1, body)
    p(x - 2, y - 2 + (1 if arm else 0), skin)
    p(x + 2, y - 2 + (0 if arm else 1), skin)
    if accent is not None:
        p(x, y - 2, accent)
    if apron is not None:
        p(x, y - 1, apron)
        p(x, y, apron)
    # waist / skirt
    if dress:
        for dx in (-2, -1, 0, 1, 2):
            p(x + dx, y, body)
            p(x + dx, y + 1, body)
        for dx in (-1, 0, 1):
            p(x + dx, y + 2, body)
        return
    for dx in (-1, 0, 1):
        p(x + dx, y, body if apron is None or dx else apron)
    # legs (walking animation)
    if step == 0:
        p(x - 1, y + 1, legs)
        p(x + 1, y + 1, legs)
        p(x - 1, y + 2, shoes)
        p(x + 1, y + 2, shoes)
    elif step == 1:
        p(x - 1, y + 1, legs)
        p(x, y + 1, legs)
        p(x - 2, y + 2, shoes)
        p(x + 1, y + 2, shoes)
    else:
        p(x, y + 1, legs)
        p(x + 1, y + 1, legs)
        p(x - 1, y + 2, shoes)
        p(x + 2, y + 2, shoes)


def tiny(px, x, y, body, hair=0, step=0):
    """3x5 sprite for the site map"""
    x, y = int(x), int(y)
    px.pset(x, y - 2, hair)
    px.pset(x, y - 1, 15)
    px.pset(x - 1, y, body)
    px.pset(x, y, body)
    px.pset(x + 1, y, body)
    px.pset(x, y + 1, body)
    if step:
        px.pset(x - 1, y + 2, 0)
    else:
        px.pset(x + 1, y + 2, 0)


_ = DAY_TICKS
