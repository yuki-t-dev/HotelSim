# ============================================================
# model.py  -  plain data objects (no game rules, no pyxel)
#   All objects must stay picklable (save / load): no lambdas inside.
# ============================================================
import random

from data import (FACILITIES, BUILDINGS, ROLES, GUEST_TYPES, SKILL_SPEED, SKILL_WAGE,
                  SLOTS, COLS, SX0, SW, CORR_TOP, CORR_BOT, CORR_Y, ENTRANCE_X)


class Building:
    """main building, annex or chapel standing on one lot of the site"""
    _n = {}

    def __init__(self, kind, lot):
        self.kind = kind
        self.spec = BUILDINGS[kind]
        self.lot = lot
        Building._n[kind] = Building._n.get(kind, 0) + 1
        self.no = Building._n[kind]
        self.floors = self.spec["floors"]
        self.cols = self.spec.get("cols", COLS)      # STEP 14: columns per row
        self.grid = [[None] * self.nslots for _ in range(self.floors)]
        self.walkway = kind == "MAIN"
        self.cams = set()

    @property
    def name(self):
        if self.kind in ("MAIN", "CHAPEL"):
            return self.spec["label"]
        return "%s%d" % (self.spec["label"], self.no)

    @property
    def prefix(self):
        if self.kind == "MAIN":
            return ""
        return ("商%d-" if self.kind == "MALL" else "別%d-") % self.no

    @property
    def nslots(self):
        return self.cols * 2

    def widen(self, cols):
        """STEP 14: old 3-column annex -> new layout (keeps every cell)"""
        old = self.cols
        if cols <= old:
            return
        new = [[None] * (cols * 2) for _ in range(self.floors)]
        for f in range(self.floors):
            seen = set()
            for c in self.grid[f]:
                if c is None or id(c) in seen:
                    continue
                seen.add(id(c))
                row, col = c.s // old, c.s % old
                c.s = row * cols + col
                for k in range(c.w):
                    new[f][c.s + k] = c
        self.grid = new
        self.cols = cols

    def is_main(self):
        return self.kind == "MAIN"

    def fixed(self):
        return self.spec.get("fixed", False)


class Cell:
    """one facility on a floor (may span several slots)"""

    def __init__(self, kind, b, f, s):
        self.kind = kind
        self.spec = FACILITIES[kind]
        self.b = b
        self.f = f
        self.s = s
        self.w = self.spec["size"]
        self.state = "clean"
        self.guest = None
        self.claimed = None
        self.seats = []
        self.broken_days = 0
        self.hygiene = 100.0
        self.closed_days = 0
        self.served_today = 0
        self.rented = False
        self.hold = None            # STEP 16: (kind, ref) - see HOLD_LABEL
        self.lv = 1                 # STEP 17: upgrade level (1-3)
        self.lunch = False          # STEP 18: open for lunch too
        self.out_plan = {}          # STEP 18: {"lunch": n, "dinner": n} outside diners
        self.tenant = None          # STEP 19: brand key renting this space
        self.tenant_warn = 0
        self.sales_today = 0

    @property
    def category(self):
        return self.spec["category"]

    @property
    def label(self):
        return self.spec["label"]

    @property
    def row(self):
        return self.s // self.b.cols

    @property
    def cx(self):
        return SX0 + (self.s % self.b.cols) * SW + SW * self.w // 2

    @property
    def door_y(self):
        return CORR_TOP if self.row == 0 else CORR_BOT

    def depth_y(self, d):
        return self.door_y - d if self.row == 0 else self.door_y + d

    def pos(self, x, y):
        return (self.b, self.f, x, y)

    def bed_pt(self):
        return self.pos(self.cx + self.spec.get("bed_dx", 0), self.depth_y(66))

    def work_pt(self):
        return self.pos(self.cx + 4, self.depth_y(32))

    def slots(self):
        return list(range(self.s, self.s + self.w))

    def number(self):
        return "%s%d%02d" % (self.b.prefix, self.f, self.s + 1)

    def is_room(self):
        return self.category == "room"

    def is_food(self):
        return self.category == "food"

    def has_hygiene(self):
        return "dirt" in self.spec

    def is_open(self):
        return self.closed_days <= 0


class Agent:
    def __init__(self, b=None, floor=0, x=ENTRANCE_X, y=CORR_Y):
        self.b = b
        self.floor = floor
        self.x = float(x)
        self.y = float(y)
        self.goal = None
        self.transit = 0
        self.dest = None
        self.trip = None
        self.hidden = False
        self.walk = 1.0
        self.wet = False

    def visible_in(self, b, f):
        return not self.hidden and self.transit <= 0 and self.b is b and self.floor == f


class Guest(Agent):
    def __init__(self, gtype, b, vip=False, price_mult=1.0, nights=None, group=None,
                 celeb=False):
        super().__init__(b)
        self.gtype = gtype
        self.spec = GUEST_TYPES[gtype]
        self.vip = vip
        self.price_mult = price_mult
        self.state = "enter"
        self.room = None
        self.nights = nights or random.choice(self.spec["nights"])
        self.desk_wait = 0
        self.angry = False
        self.checkout_t = None
        self.paid = 0
        prefs = self.spec["food_pref"]
        self.pref = random.choices(list(prefs), weights=list(prefs.values()))[0]
        self.meals = set()
        self.sick = False
        self.group = group
        self.want = "SINGLE"
        self.how = "ok"
        self.celeb = celeb
        self.robbed = False
        self.bath = None
        self.spa = False
        self.hungry = False         # STEP 13: wanted dinner, restaurant full
        self.couple = False         # STEP 16: bride & groom staying the night
        self.moved = False          # STEP 16: asked to change rooms
        self.concierge = False      # STEP 17: shown to the room by the concierge
        self.kiosk = False          # STEP 17: used the check-in kiosk
        self.swam = False           # STEP 20: used the pool

    @property
    def party(self):
        return 1 if self.want == "SINGLE" else 2


class Staff(Agent):
    _id = 0

    def __init__(self, role, skill, name):
        super().__init__()
        Staff._id += 1
        self.id = Staff._id
        self.role = role
        self.skill = skill
        self.name = name
        self.fatigue = random.uniform(0, 15)
        self.exp = 0
        self.post = None
        self.state = "standby"
        self.task = None
        self.timer = 0
        self.seat = None
        self.hidden = True
        self.bonus = 0
        self.patrol = None
        self.wait = 0

    def wage(self):
        return int(ROLES[self.role]["wage"] * SKILL_WAGE[self.skill - 1]) + self.bonus

    def speed(self):
        sp = SKILL_SPEED[self.skill - 1]
        if self.fatigue > 60:
            sp *= 1.0 - 0.5 * (min(self.fatigue, 100) - 60) / 40
        return sp

    def stars(self):
        return "★" * self.skill


class Visitor(Agent):
    """day visitor (meeting / party / wedding attendee). No overnight stay."""

    def __init__(self, entry_b, cell, seat, leave_t, color, booking=None, wrole=None):
        super().__init__(entry_b)
        self.cell = cell
        self.leave_t = leave_t
        self.color = color
        self.state = "enter"
        self.goal = cell.pos(*seat)
        self.walk = 3.0
        self.booking = booking
        self.wrole = wrole
