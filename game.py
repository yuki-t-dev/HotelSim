# ============================================================
# game.py  -  game rules (no pyxel here -> can be tested headless)
#
#   The hotel is made of BUILDINGS standing on LOTS of the site.
#     positions / goals are (building, floor, x, y)
#   A day ends with close_day() -> (morning snapshot for SAVE) -> begin_day().
#   Timers (lambdas) only live during a day, so the snapshot is always picklable.
# ============================================================
import math
import pickle
import random

from data import (FACILITIES, BUILDINGS, ROLES, BREAK_RULES, EXP_LV, STAR_GOALS,
                  FLOOR_LIMIT, NAMES, WEEKDAYS, WEEKDAY_LABEL, DAY_DEMAND, DAY_BIZ,
                  SEASON_DAYS, SEASONS, SEASON_FIRST_MONTH, GUEST_TYPES, FOOD_KINDS,
                  SLOTS, COLS, LOBBY_RESERVED,
                  SX0, CORR_TOP, CORR_Y, STAIR_X, ENTRANCE_X, WALK, STAIR_T,
                  DAY_TICKS, CHECKOUT_RANGE, CLEAN_T, CHECKIN_T, DESK_PATIENCE,
                  COOK_PREP, HYGIENE_DAILY_DROP, HYGIENE_DANGER, POISON_MAX_P,
                  POISON_CLOSE_DAYS, POISON_REP, POISON_COMP, DEEP_CLEAN_COST,
                  FAC_CLEAN_T, FAC_CLEAN_GAIN, MAIN_LOT, START_LOTS,
                  LAND_BASE, LAND_STEP, OUT_BASE, OUT_PER_LOT, DEMOLISH_REFUND,
                  LOT_TRAITS, TRAITS, OCEAN_PRICE, OCEAN_SAT, LOT_FACILITIES, GARDEN_SAT,
                  PARKING_DEMAND, WALKWAY_COST, WEATHERS, SEASON_WEATHER, WET_SAT, SNOW_SLOW,
                  ROOM_TIER, FAIR_MULT, PRICE_START, PRICE_RANGE, PRICE_STEP,
                  ROOM_KINDS, ROOM_WANT, SUITE_WANT, ROKUYO,
                  CAMERA_COST, CAMERA_UPKEEP, PATROL_SEC, CAM_SEC_WATCHED, CAM_SEC_ALONE,
                  SEC_MAX, PATROL_WAIT, BATH_T, RIVAL_DAY, ROUTES, ROUTE_ORDER,
                  DIFFICULTY, SAVE_VERSION, OCC_MAX, DEMAND_CAP, QUEUE_PER_FRONT,
                  QUEUE_BASE, QUEUE_RETRY, ANGRY_REP_CAP, HOT_DEMAND,
                  HOLD_LABEL, MOVE_COMP, UPGRADES, ROOM_LV_SAT, ROOM_LV_PRICE, KIOSK_T,
                  KIOSK_UPKEEP, CONCIERGE_UPKEEP, CONCIERGE_SAT,
                  LUNCH_T, DINNER_KINDS, OUTSIDE, DROPIN_P, OUTSIDE_COLOR,
                  clamp, approach, in_corridor, lot_dist)
from model import Building, Cell, Guest, Staff, Visitor
from events import EventManager, poisoning_popup
import bookings as bk
import security as sec
import resort as rs
import shops as sh
import leisure as ls
from data import TENANT_SAT, POOL_T, NIGHT_POOL_T, GYM_CAP

VERSION = "STEP 20"


class Game:
    def __init__(self, seed=None, difficulty="NORMAL", tutorial=True):
        if seed is not None:
            random.seed(seed)
        Building._n = {}
        self.diff_key = difficulty
        self.diff = DIFFICULTY[difficulty]
        self.tutorial = tutorial
        self.tut_step = 0
        self.tut_flags = set()
        self.day = 1
        self.t = 600
        self.cash = float(self.diff["cash"])
        self.debt = 0.0
        self.over_limit_nights = 0
        self.rep = 50.0
        self.star = 1
        self.prices = dict(PRICE_START)
        self.break_idx = 1
        self.main = Building("MAIN", MAIN_LOT)
        self.buildings = [self.main]
        self.lots = set(START_LOTS)
        self.lot_fac = {}
        self.weather = {}
        self.guests = []
        self.staff = []
        self.visitors = []
        self.desk_queue = []
        self.arrivals = []
        self.timers = []
        self.candidates = []
        self.bookings = []
        self.followups = []
        self.bridal_boom = 0
        self.crime_wave = 0
        self.sec_flash = None
        self.stats = {}
        self.reviews = []
        self.rival = None
        self.route = None
        self.free_play = False
        self.popups = []            # visual: (b, f, x, y, stars, frames) review bubbles
        self.confetti = None        # visual: (cell, frames)
        self.fire_fx = None         # visual: (cell, frames)
        self.msgs = []
        self.report = None
        self.cleared = False
        self.bankrupt = False
        self.events = EventManager()
        self.pending = []
        self.cheap_food_days = 0
        self.food_boom = None
        self.desk_lv = 1            # STEP 17: front desk upgrade level
        self.kiosk_t = 0
        self.gym_members = 0        # STEP 20
        self._snap = None
        self.reset_daily()
        self.forecast(1)
        self.place("SINGLE", self.main, 1, 0)
        self.place("DOUBLE", self.main, 1, 1)
        self.new_candidates()
        for role, post in (("FRONT", ("DESK",)), ("CLEANER", ("FLOOR", self.main, 1))):
            st = Staff(role, 1, self.pick_name())
            self.staff.append(st)
            self.assign(st, post)
        self.plan_arrivals()
        self.log("ピクセルホテルへようこそ！（%s）" % self.diff["label"])

    # ---------------- save / load ----------------
    def __getstate__(self):
        d = dict(self.__dict__)
        d["_snap"] = None
        d["timers"] = []
        d["popups"] = []
        d["confetti"] = None
        d["fire_fx"] = None
        d["sec_flash"] = None
        return d

    def take_snapshot(self):
        try:
            self._snap = pickle.dumps(self, protocol=4)
        except Exception as e:      # should not happen; keep the old snapshot
            self.log("（セーブ用の記録に失敗：%s）" % e.__class__.__name__)

    def save_data(self):
        """bytes for a save file (this morning's state)"""
        if self._snap is None:
            self.take_snapshot()
        meta = dict(ver=SAVE_VERSION, day=self.day, star=self.star, cash=int(self.cash),
                    diff=self.diff["label"], rep=round(self.rep, 1))
        return pickle.dumps(dict(meta=meta, game=self._snap), protocol=4)

    @staticmethod
    def load_data(blob):
        d = pickle.loads(blob)
        g = pickle.loads(d["game"])
        Building._n = {}
        for b in g.buildings:
            Building._n[b.kind] = max(Building._n.get(b.kind, 0), b.no)
        g._snap = d["game"]
        g.compat()
        g.begin_day()
        g.log("ロードしました：%d日目の朝から再開" % g.day)
        return g

    def compat(self):
        """fill attributes added after the save was written"""
        defaults = dict(d_lost_value=0, d_angry_pen=0.0, d_lost_busy=0, d_hungry=0,
                        demand_raw=0.0, demand_cap=0.0)
        for k, v in defaults.items():
            if not hasattr(self, k):
                setattr(self, k, v)
        for gg in self.guests:
            if not hasattr(gg, "hungry"):
                gg.hungry = False
            for k in ("couple", "moved"):            # STEP 16
                if not hasattr(gg, k):
                    setattr(gg, k, False)
        for c in self.cells():
            if not hasattr(c, "hold"):
                c.hold = None
            if not hasattr(c, "lv"):                 # STEP 17
                c.lv = 1
        for k, v in (("d_leisure", 0), ("d_pool_out", 0), ("d_gym", 0),
                     ("gym_members", 0)):                 # STEP 20
            if not hasattr(self, k):
                setattr(self, k, v)
        for gg in self.guests:
            if not hasattr(gg, "swam"):
                gg.swam = False
        for k, v in (("d_shop", 0), ("d_umbrella", 0), ("d_vips", 0),
                     ("d_tenant_visitors", 0)):          # STEP 19
            if not hasattr(self, k):
                setattr(self, k, v)
        for c in self.cells():
            for k, v in (("tenant", None), ("tenant_warn", 0), ("sales_today", 0)):
                if not hasattr(c, k):
                    setattr(c, k, v)
        for c in self.cells():                       # STEP 18
            c.spec = FACILITIES[c.kind]              # pick up new data (lunch prices ...)
            for k, v in (("lunch", False), ("out_plan", {})):
                if not hasattr(c, k):
                    setattr(c, k, v)
        for k in FOOD_KINDS:
            self.d_meals.setdefault(k, 0)
        if not hasattr(self, "d_out"):
            self.d_out = {"lunch": 0, "dinner": 0}
            self.d_out_food = 0
            self.d_dropins = 0
        if not hasattr(self, "desk_lv"):
            self.desk_lv = 1
            self.kiosk_t = 0
        for gg in self.guests:
            for k in ("concierge", "kiosk"):
                if not hasattr(gg, k):
                    setattr(gg, k, False)
        for b in self.buildings:                     # STEP 14
            if not hasattr(b, "cols"):
                b.cols = COLS
            want = BUILDINGS[b.kind].get("cols", COLS)
            if b.cols < want:
                b.widen(want)

    @staticmethod
    def read_meta(blob):
        return pickle.loads(blob)["meta"]

    # ---------------- helpers ----------------
    def log(self, m):
        self.msgs.append(m)
        self.msgs = self.msgs[-4:]

    def reset_daily(self):
        self.d_income = 0.0
        self.d_food = 0.0
        self.d_meals = {k: 0 for k in FOOD_KINDS}
        self.d_poison = 0
        self.d_guests = 0
        self.d_types = {k: 0 for k in GUEST_TYPES}
        self.d_lost_full = 0
        self.d_lost_angry = 0
        self.d_rep0 = self.rep
        self.d_rental = 0
        self.d_booking = []
        self.d_wet = 0
        self.d_how = {"upgrade": 0, "swap": 0, "downgrade": 0}
        self.d_rooms_by = {k: 0 for k in ROOM_KINDS}
        self.d_sec = {"prevented": 0, "happened": 0}
        self.d_resort = 0
        self.d_reviews = []
        self.d_lost_value = 0       # STEP 13: rooms we could have sold
        self.d_angry_pen = 0.0      # STEP 13: rep lost to desk walk-outs today
        self.d_lost_busy = 0        # STEP 13: gave up because the lobby was packed
        self.d_hungry = 0           # STEP 13: wanted to eat, no seat
        self.d_leisure = 0          # STEP 20
        self.d_pool_out = 0
        self.d_gym = 0
        self.d_shop = 0             # STEP 19
        self.d_umbrella = 0
        self.d_vips = 0
        self.d_tenant_visitors = 0
        self.d_out = {"lunch": 0, "dinner": 0}   # STEP 18: outside diners served
        self.d_out_food = 0
        self.d_dropins = 0
        for c in self.cells() if hasattr(self, "buildings") else []:
            c.served_today = 0
            c.sales_today = 0
            c.rented = False
        for a in getattr(self, "guests", []):
            a.shopped = set()                        # STEP 19: may shop again tomorrow

    def pick_name(self):
        used = {s.name for s in self.staff} | {c.name for c in self.candidates}
        free = [n for n in NAMES if n not in used]
        return random.choice(free) if free else "X%d" % random.randint(10, 99)

    def floor_cells(self, b, f):
        return [c for s, c in enumerate(b.grid[f]) if c and c.s == s]

    def cells(self, kinds=None, category=None):
        for b in self.buildings:
            for f in range(b.floors):
                for c in self.floor_cells(b, f):
                    if kinds is not None and c.kind not in kinds:
                        continue
                    if category is not None and c.category != category:
                        continue
                    yield c

    def exists(self, c):
        return c.b in self.buildings and c.b.grid[c.f][c.s] is c

    def rooms(self):
        return list(self.cells(category="room"))

    def food_cells(self):
        return list(self.cells(category="food"))

    def has_bar(self):
        return any(True for _ in self.cells(("BAR",)))

    def hygiene_cells(self):
        return [c for c in self.cells() if c.has_hygiene()]

    def sellable_rooms(self):
        """free rooms that are clean or will be cleaned today (STEP 13)"""
        return sum(1 for c in self.rooms() if c.guest is None and c.state in ("clean", "dirty"))

    def free_room_count(self):
        return sum(1 for c in self.rooms() if c.state == "clean" and c.guest is None)

    def add_timer(self, t, fn):
        self.timers.append((t, fn))
        self.timers.sort(key=lambda x: x[0])

    def max_floor(self, b):
        return FLOOR_LIMIT[self.star] if b.is_main() else b.floors - 1

    def break_rule(self):
        return BREAK_RULES[self.break_idx]

    def floor_stats(self, b, f):
        cells = self.floor_cells(b, f)
        rooms = [c for c in cells if c.is_room()]
        hyg = [c for c in cells if c.has_hygiene()]
        return {
            "rooms": len(rooms),
            "occ": sum(1 for c in rooms if c.state == "occupied"),
            "dirty": sum(1 for c in rooms if c.state == "dirty"),
            "broken": sum(1 for c in rooms if c.state == "broken"),
            "cleaners": self.post_count(("FLOOR", b, f)),
            "food_low": min([c.hygiene for c in hyg], default=100),
            "food_closed": any(not c.is_open() for c in hyg),
            "cam": f in b.cams,
        }

    def building_stats(self, b):
        rooms = [c for c in self.rooms() if c.b is b]
        return (sum(1 for c in rooms if c.state == "occupied"), len(rooms),
                sum(1 for c in rooms if c.state == "dirty"))

    # ---------------- calendar ----------------
    def weekday(self, day=None):
        d = self.day if day is None else day
        return WEEKDAYS[(d - 1) % 7]

    def weekday_label(self, day=None):
        d = self.day if day is None else day
        return WEEKDAY_LABEL[(d - 1) % 7]

    def rokuyo(self, day=None):
        d = self.day if day is None else day
        return ROKUYO[(d + 3) % 6]

    def season_info(self, day=None):
        d = self.day if day is None else day
        return SEASONS[((d - 1) // SEASON_DAYS) % len(SEASONS)]

    def season(self, day=None):
        return self.season_info(day)[0]

    def season_label(self, day=None):
        return self.season_info(day)[3]

    def day_of_season(self, day=None):
        d = self.day if day is None else day
        return (d - 1) % SEASON_DAYS + 1

    def month(self, day=None):
        d = self.day if day is None else day
        m = SEASON_FIRST_MONTH[self.season(d)] + (self.day_of_season(d) - 1) * 3 // SEASON_DAYS
        return (m - 1) % 12 + 1

    def demand_mult(self, day=None):
        d = self.day if day is None else day
        return DAY_DEMAND[(d - 1) % 7] * self.season_info(d)[1]

    def biz_share(self, day=None):
        d = self.day if day is None else day
        return DAY_BIZ[(d - 1) % 7]

    # ---------------- prices / room types ----------------
    def fair_price(self):
        return 50 + 15 * (self.star - 1)

    def fair(self, kind):
        return int(round(self.fair_price() * FAIR_MULT[kind] / 5.0)) * 5

    def change_price(self, kind, sign):
        lo, hi = PRICE_RANGE[kind]
        self.prices[kind] = clamp(self.prices[kind] + sign * PRICE_STEP[kind], lo, hi)

    def price_factor(self, kind):
        f = self.fair(kind)
        return math.exp(-1.6 * (self.prices[kind] - f) / f)

    def is_ocean(self, c):
        return LOT_TRAITS.get(c.b.lot) == "OCEAN"

    def room_price(self, c, kind=None):
        p = self.prices[kind or c.kind] * (OCEAN_PRICE if self.is_ocean(c) else 1.0)
        if kind is None or kind == c.kind:
            p *= ROOM_LV_PRICE[getattr(c, "lv", 1)]          # STEP 17: luxury furniture
        return p

    def suite_want_p(self, gtype):
        f = math.exp(-2.0 * (self.prices["SUITE"] - self.fair("SUITE")) / self.fair("SUITE"))
        return clamp(SUITE_WANT[gtype] * f, 0.0, 0.5)

    def want_weights(self, gtype):
        out = {}
        for k, w in ROOM_WANT[gtype].items():
            out[k] = w * clamp(math.exp(-1.5 * (self.prices[k] - self.fair(k)) / self.fair(k)),
                               0.1, 3.0)
        return out

    def pick_want(self, gtype):
        if random.random() < self.suite_want_p(gtype):
            return "SUITE"
        ws = self.want_weights(gtype)
        return random.choices(list(ws), weights=list(ws.values()))[0]

    # ---------------- weather ----------------
    def forecast(self, upto):
        for d in range(1, upto + 8):
            if d not in self.weather:
                w = SEASON_WEATHER[self.season(d)]
                self.weather[d] = random.choices(list(w), weights=list(w.values()))[0]

    def weather_at(self, day=None):
        d = self.day if day is None else day
        if d not in self.weather:
            self.forecast(d)
        return self.weather[d]

    def covered(self, lot_a, lot_b):
        ba, bb = self.building_at(lot_a), self.building_at(lot_b)
        return bool(ba and bb and ba.walkway and bb.walkway)

    def walkway_cost(self, b):
        return WALKWAY_COST * max(1, lot_dist(b.lot, self.main.lot))

    def build_walkway(self, b):
        cost = self.walkway_cost(b)
        if b.walkway or self.cash < cost:
            self.log("渡り廊下を作れません")
            return False
        self.cash -= cost
        b.walkway = True
        self.log("%sに渡り廊下を作りました（-$%d）" % (b.name, cost))
        return True

    # ---------------- lot traits / outdoor facilities ----------------
    def trait(self, lot):
        return LOT_TRAITS.get(lot, "NORMAL")

    def can_build_lotfac(self, lot, kind):
        spec = LOT_FACILITIES[kind]
        if lot not in self.lots:
            return False, "未購入"
        if self.building_at(lot) or lot in self.lot_fac:
            return False, "使用中"
        if self.star < spec["star"]:
            return False, "要★%d" % spec["star"]
        if self.cash < spec["cost"]:
            return False, "資金不足"
        return True, ""

    def build_lotfac(self, lot, kind):
        ok, why = self.can_build_lotfac(lot, kind)
        if not ok:
            self.log("建設できません：" + why)
            return False
        self.cash -= LOT_FACILITIES[kind]["cost"]
        self.lot_fac[lot] = kind
        self.log("%sを作りました" % LOT_FACILITIES[kind]["label"])
        return True

    def remove_lotfac(self, lot):
        kind = self.lot_fac.pop(lot, None)
        if kind:
            refund = int(LOT_FACILITIES[kind]["cost"] * DEMOLISH_REFUND)
            self.cash += refund
            self.log("%sを撤去しました（+$%d）" % (LOT_FACILITIES[kind]["label"], refund))

    def neighbors(self, lot):
        lx, ly = lot
        return [(lx + dx, ly + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]

    def garden_bonus(self, b):
        return sum(GARDEN_SAT * (2 if self.trait(l) == "FOREST" else 1)
                   for l in self.neighbors(b.lot) if self.lot_fac.get(l) == "GARDEN")

    def parking_mult(self):
        ps = sorted((2 if self.trait(l) == "STATION" else 1)
                    for l, k in self.lot_fac.items() if k == "PARKING")[-2:]
        return 1.0 + PARKING_DEMAND * sum(ps)

    # ---------------- weddings ----------------
    def chapel_hall(self):
        for b in self.buildings:
            if b.kind == "CHAPEL":
                return b.grid[0][0]
        return None

    def chapel_garden(self):
        hall = self.chapel_hall()
        return bool(hall and any(self.lot_fac.get(l) == "GARDEN"
                                 for l in self.neighbors(hall.b.lot)))

    def has_venue(self):
        return self.chapel_hall() is not None or any(True for _ in self.cells(("SHRINE",)))

    # ---------------- security ----------------
    def guards_on(self, post):
        return [s for s in self.staff if s.post == post and s.role == "GUARD"
                and s.state not in ("rest", "go_rest")]

    def guard_count(self):
        return sum(1 for s in self.staff if s.role == "GUARD" and s.post is not None)

    def monitored(self):
        return any(self.guards_on(("FAC", c)) for c in self.cells(category="security"))

    def camera_share(self, b):
        n = self.max_floor(b) + 1
        return len([f for f in b.cams if f < n]) / max(1, n)

    def security(self, b):
        s = PATROL_SEC * len(self.guards_on(("PATROL", b)))
        s += self.camera_share(b) * (CAM_SEC_WATCHED if self.monitored() else CAM_SEC_ALONE)
        return min(SEC_MAX, s)

    def min_security(self):
        bs = [b for b in self.buildings if not b.fixed()]
        return min(self.security(b) for b in bs) if bs else 0.0

    def who_prevented(self, b):
        gs = self.guards_on(("PATROL", b))
        if gs:
            return "警備員%s" % random.choice(gs).name
        return "防犯カメラ"

    def add_camera(self, b, f):
        if f in b.cams or self.cash < CAMERA_COST:
            self.log("防犯カメラを付けられません")
            return False
        self.cash -= CAMERA_COST
        b.cams.add(f)
        self.log("%s%dFに防犯カメラを付けました（-$%d）" % (b.prefix, f, CAMERA_COST))
        return True

    def add_cameras_all(self, b):
        fs = [f for f in range(self.max_floor(b) + 1) if f not in b.cams]
        cost = CAMERA_COST * len(fs)
        if not fs or self.cash < cost:
            self.log("防犯カメラを付けられません")
            return False
        self.cash -= cost
        b.cams.update(fs)
        self.log("%sの全階に防犯カメラ（-$%d）" % (b.name, cost))
        return True

    def celeb_check(self):
        celebs = [g for g in self.guests if g.celeb and g.state in ("in_room", "to_room")]
        for c in self.held_cells("CELEB"):
            self.unhold(c)
        if not celebs:
            if any(g.celeb for g in self.guests):
                self.rep = clamp(self.rep - 2, 0, 100)
                self.pending.append({"title": "有名人の宿泊：部屋がなかった",
                                     "lines": ["用意できる部屋がなく、帰ってしまいました。",
                                               "評判 -2"],
                                     "choices": [("OK…", True, None)]})
            return
        g = celebs[0]
        s = self.security(g.room.b) if g.room else 0.0
        if random.random() < s + 0.1:
            self.rep = clamp(self.rep + 4, 0, 100)
            popup = {"title": "有名人の宿泊：大成功！",
                     "lines": ["警備のおかげで、記者に見つからず静かに過ごせました。",
                               "「また泊まりたい」とSNSで話題に！ 評判 +4"],
                     "choices": [("OK", True, None)]}
        else:
            self.rep = clamp(self.rep - 4, 0, 100)
            popup = {"title": "!! 有名人の宿泊が記者に見つかった !!",
                     "lines": ["ホテルの前に記者が押しかけ、大騒ぎに…",
                               "防犯レベル：%d%%　評判 -4" % (s * 100)],
                     "choices": [("OK…", True, None)]}
        self.events.note(self, popup)
        self.pending.append(popup)

    # ---------------- bank ----------------
    def credit_limit(self):
        base = 2000 + 2000 * (self.star - 1) + max(0, self.rep - 50) * 30
        return int(base * self.diff["credit"])

    def interest_rate(self):
        return 0.012 - 0.001 * (self.star - 1)

    def borrow(self, amount):
        if self.credit_limit() - self.debt < amount:
            self.log("銀行：融資枠を超えています")
            return False
        self.debt += amount
        self.cash += amount
        self.log("$%d を借り入れました" % amount)
        return True

    def repay(self, amount):
        amount = int(min(amount, self.debt, max(0, self.cash)))
        if amount <= 0:
            self.log("返済できる額がありません")
            return False
        self.debt -= amount
        self.cash -= amount
        self.log("$%d を返済しました" % amount)
        return True

    # ---------------- site / land ----------------
    def building_at(self, lot):
        for b in self.buildings:
            if b.lot == lot:
                return b
        return None

    def land_price(self, lot):
        return (LAND_BASE + LAND_STEP * lot_dist(lot, MAIN_LOT) +
                TRAITS[self.trait(lot)]["extra"])

    def lot_adjacent(self, lot):
        return any(l in self.lots for l in self.neighbors(lot))

    def can_buy(self, lot):
        if lot in self.lots:
            return False, "購入済み"
        if not self.lot_adjacent(lot):
            return False, "隣の区画から順に購入"
        if self.cash < self.land_price(lot):
            return False, "資金不足"
        return True, ""

    def buy_lot(self, lot):
        ok, why = self.can_buy(lot)
        if not ok:
            self.log("購入できません：" + why)
            return False
        self.cash -= self.land_price(lot)
        self.lots.add(lot)
        self.log("土地を購入しました（-$%d）" % self.land_price(lot))
        return True

    def can_build_building(self, lot, kind):
        spec = BUILDINGS[kind]
        if lot not in self.lots:
            return False, "未購入"
        if self.building_at(lot) or lot in self.lot_fac:
            return False, "使用中"
        if kind == "CHAPEL" and self.chapel_hall() is not None:
            return False, "1棟まで"
        if self.star < spec["star"]:
            return False, "要★%d" % spec["star"]
        if self.cash < spec["cost"]:
            return False, "資金不足"
        return True, ""

    def build_building(self, lot, kind):
        ok, why = self.can_build_building(lot, kind)
        if not ok:
            self.log("建設できません：" + why)
            return None
        self.cash -= BUILDINGS[kind]["cost"]
        b = Building(kind, lot)
        self.buildings.append(b)
        if kind == "CHAPEL":
            self.place("CHAPEL_HALL", b, 0, 0)
        self.log("%sを建設しました" % b.name)
        return b

    # ---------------- staff ----------------
    def new_candidates(self):
        self.candidates = []
        names = list(ROLES)
        for r in names + [random.choice(names), random.choice(names)]:
            p = random.random()
            skill = 1 if p < 0.6 else (2 if p < 0.9 else 3)
            if self.star == 1 and skill == 3:
                skill = 2
            self.candidates.append(Staff(r, skill, self.pick_name()))

    def hire_fee(self, st):
        return st.wage() * 3

    def hire(self, st, post=None):
        fee = self.hire_fee(st)
        if self.cash < fee:
            self.log("資金が足りず雇えません")
            return False
        if post and not self.can_assign(st, post):
            self.log("%sはそこに配置できません" % st.name)
            return False
        self.cash -= fee
        self.candidates.remove(st)
        self.staff.append(st)
        self.log("%sを雇いました（%s %s）" % (st.name, ROLES[st.role]["label"], st.stars()))
        if post:
            self.assign(st, post)
        return True

    def post_count(self, post, role=None):
        return sum(1 for s in self.staff
                   if s.post == post and (role is None or s.role == role))

    def post_roles(self, post):
        if post[0] == "FAC":
            return post[1].spec.get("roles", {})
        return {name: spec["post_max"] for name, spec in ROLES.items()
                if spec["post"] == post[0]}

    def assign_block(self, st, post):
        roles = self.post_roles(post)
        if st.role not in roles:
            return "職種違い"
        lim = roles[st.role]
        if lim is not None and self.post_count(post, st.role) >= lim:
            return "満員"
        if post[0] == "FAC" and st.role == "COOK":
            need = post[1].spec.get("cook_skill", 1)
            if st.skill < need:
                return "要料理人%s" % ("★" * need)
        return ""

    def can_assign(self, st, post):
        return self.assign_block(st, post) == ""

    def post_name(self, post):
        if post is None:
            return "待機"
        if post[0] == "DESK":
            return "フロント"
        if post[0] == "FLOOR":
            return "%s%dF" % (post[1].prefix, post[2])
        if post[0] == "PATROL":
            return "%s巡回" % post[1].name
        c = post[1]
        return "%s(%s%dF)" % (c.label, c.b.prefix, c.f)

    def release(self, st):
        if st.task is not None:
            if isinstance(st.task, Guest) and st.task.state == "checkin":
                st.task.state = "queue_desk"
                self.desk_queue.insert(0, st.task)
            elif isinstance(st.task, Cell):
                if st.task.claimed is st:
                    st.task.claimed = None
        st.task = None
        if st.seat is not None:
            if st in st.seat.seats:
                st.seat.seats.remove(st)
            st.seat = None

    def assign(self, st, post):
        self.release(st)
        st.post = post
        st.hidden = False
        st.patrol = None
        if st.b is None or st.state == "standby":
            st.b, st.floor = self.main, 0
            st.x, st.y = float(ENTRANCE_X), float(CORR_Y)
            st.transit, st.trip = 0, None
        st.state = "go_post"
        st.goal = self.post_pos(st)

    def unassign(self, st):
        self.release(st)
        st.post = None
        st.state = "standby"
        st.hidden = True
        st.transit, st.trip = 0, None

    def fire(self, st):
        self.unassign(st)
        self.staff.remove(st)
        self.log("%sを解雇しました" % st.name)

    def new_patrol_point(self, st):
        b = st.post[1]
        top = self.max_floor(b)
        floors = [f for f in range(top + 1) if self.floor_cells(b, f)] or [0]
        f = random.choice(floors)
        return (b, f, random.randint(SX0 + 10, ENTRANCE_X - 20), CORR_Y + random.choice((-3, 3)))

    def post_pos(self, st):
        p = st.post
        same = [s for s in self.staff if s.post == p and s.role == st.role]
        i = same.index(st) if st in same else 0
        if p[0] == "DESK":
            return (self.main, 0, SX0 + 24 + 22 * i, CORR_TOP - 12)
        if p[0] == "FLOOR":
            return (p[1], p[2], STAIR_X + 10 + 6 * i, CORR_Y - 3)
        if p[0] == "PATROL":
            if st.patrol is None:
                st.patrol = self.new_patrol_point(st)
            return st.patrol
        c = p[1]
        if st.role == "COOK":
            return c.pos(c.cx - 8 + 16 * i, c.depth_y(70))
        if st.role == "GUARD":
            return c.pos(c.cx - 8 + 16 * i, c.depth_y(56))
        return c.pos(c.cx - 20 + 8 * i, c.depth_y(20))

    def staffroom_seat(self, st):
        rooms = [c for c in self.cells(category="staff") if len(c.seats) < c.spec["seats"]]
        if not rooms:
            return None
        here = st.b.lot if st.b else MAIN_LOT
        return min(rooms, key=lambda c: (lot_dist(here, c.b.lot), abs(c.f - st.floor)))

    def send_rest(self, st, forced=False):
        room = self.staffroom_seat(st)
        if room is None:
            if forced:
                self.log("休憩室に空きがありません")
            return False
        self.release(st)
        room.seats.append(st)
        st.seat = room
        st.state = "go_rest"
        i = room.seats.index(st)
        st.goal = room.pos(room.cx - 6 + 6 * i, room.depth_y(60))
        return True

    # ---------------- facilities in buildings ----------------
    def slot_free(self, b, f, s):
        return b.grid[f][s] is None and not (b.is_main() and f == 0 and s in LOBBY_RESERVED)

    def anchor_for(self, b, f, s, kind):
        n = FACILITIES[kind]["size"]
        cols = b.cols
        row, col = s // cols, s % cols
        for c0 in (col, col - n + 1):
            if c0 < 0 or c0 + n > cols:
                continue
            a = row * cols + c0
            if all(self.slot_free(b, f, a + k) for k in range(n)):
                return a
        return None

    def can_build(self, b, f, s, kind):
        spec = FACILITIES[kind]
        if b.fixed():
            return False, "この建物には置けません"
        if b.grid[f][s] is not None:
            return False, "使用中"
        if b.is_main() and f == 0 and s in LOBBY_RESERVED:
            return False, "フロント"
        if f > self.max_floor(b):
            return False, "未開放の階"
        if b.kind == "MALL" and not spec.get("mall_ok"):
            return False, "商業棟には不可"
        if b.kind == "ANNEX" and not spec["annex_ok"]:
            return False, "別館には不可"
        if self.star < spec["star"]:
            return False, "要★%d" % spec["star"]
        if b.is_main() and f == 0 and not spec["lobby_ok"]:
            return False, "ロビー不可"
        if self.anchor_for(b, f, s, kind) is None:
            return False, "空き%d枠必要" % spec["size"]
        mx = spec.get("max_count")
        if mx is not None and len(list(self.cells((kind,)))) >= mx:
            return False, "最大%d軒" % mx
        if self.cash < spec["cost"]:
            return False, "資金不足"
        return True, ""

    def place(self, kind, b, f, anchor):
        c = Cell(kind, b, f, anchor)
        for k in c.slots():
            b.grid[f][k] = c
        return c

    def build(self, b, f, s, kind):
        ok, why = self.can_build(b, f, s, kind)
        if not ok:
            self.log("建設できません：" + why)
            return False
        self.cash -= FACILITIES[kind]["cost"]
        self.place(kind, b, f, self.anchor_for(b, f, s, kind))
        self.log("%s%dFに%sを建設しました" % (b.prefix, f, FACILITIES[kind]["label"]))
        return True

    def demolish_block(self, c):
        if c.spec.get("buildable") is False:
            return "撤去できません"
        if c.guest is not None or c.state == "occupied":
            return "宿泊客がいます"
        if c.claimed is not None:
            return "清掃中です"
        if getattr(c, "hold", None) is not None and c.hold[0] != "PLAYER":
            return "予約で確保中です"
        if any(s.post == ("FAC", c) for s in self.staff):
            return "スタッフを外してください"
        if c.seats:
            return "休憩中のスタッフがいます"
        if any(v.cell is c and v.state != "gone" for v in self.visitors):
            return "利用客がいます"
        if c.rented or bk.cell_in_use(self, c):
            return "本日の予約で使用中"
        return ""

    def demolish_refund(self, c):
        return int(c.spec["cost"] * DEMOLISH_REFUND)

    def demolish(self, c):
        why = self.demolish_block(c)
        if why:
            self.log("撤去できません：" + why)
            return False
        for k in c.slots():
            c.b.grid[c.f][k] = None
        refund = self.demolish_refund(c)
        self.cash += refund
        self.log("%sを撤去しました（+$%d）" % (c.label, refund))
        return True

    # ---------------- demand ----------------
    def raw_demand(self, day=None):
        """guests who WANT to stay (before the capacity cap)"""
        rooms = self.rooms()
        occ = 0.45 + 0.008 * (self.rep - 50) + 0.06 * (self.star - 1)
        if rooms:
            pf = sum(self.price_factor(c.kind) for c in rooms) / len(rooms)
        else:
            pf = self.price_factor("SINGLE")
        occ = clamp(occ * clamp(pf, 0.15, 1.6), 0.05, OCC_MAX)
        wmult = WEATHERS[self.weather_at(day)]["demand"]
        return max(0.0, (len(rooms) * occ + 1.5) * self.demand_mult(day) * wmult *
                   self.parking_mult() * rs.review_mult(self) * rs.rival_mult(self) *
                   self.diff["demand"])

    def tonight_capacity(self):
        """rooms that can still be sold tonight (morning estimate)"""
        rooms = self.rooms()
        staying = sum(1 for x in self.guests
                      if x.state in ("in_room", "to_room") and x.checkout_t is None)
        broken = sum(1 for c in rooms if c.state == "broken")
        held = sum(b.rooms for b in bk.today_bookings(self))
        return max(0, len(rooms) - staying - broken - held)

    def expected_guests(self, day=None):
        raw = self.raw_demand(day)
        if day is None or day == self.day:
            return min(raw, DEMAND_CAP * self.tonight_capacity() + 1)
        return min(raw, DEMAND_CAP * len(self.rooms()) + 1)

    def hot_demand(self):
        """True when far more guests want to come than we can host"""
        cap = getattr(self, "demand_cap", 0) or self.tonight_capacity()
        return getattr(self, "demand_raw", 0) > HOT_DEMAND * max(1, cap)

    def add_arrival(self, t, gtype, **kw):
        self.arrivals.append((t, gtype, kw))
        self.arrivals.sort(key=lambda a: a[0])

    def plan_arrivals(self):
        self.arrivals = []
        self.demand_raw = self.raw_demand()
        self.demand_cap = self.tonight_capacity()
        n = max(0, int(round(random.gauss(self.expected_guests(), 1.2))))
        biz = self.biz_share()
        if any(k == "PARKING" and self.trait(l) == "STATION" for l, k in self.lot_fac.items()):
            biz = min(0.9, biz + 0.1)
        for _ in range(n):
            gt = "BUSINESS" if random.random() < biz else "TOURIST"
            self.add_arrival(random.randint(*GUEST_TYPES[gt]["arrive"]), gt)

    # ---------------- movement ----------------
    def step_to(self, a, tx, ty):
        sp = WALK * a.walk
        if abs(a.x - tx) > 0.01:
            if in_corridor(a.y):
                a.x = approach(a.x, tx, sp)
            else:
                a.y = approach(a.y, CORR_Y, sp)
            return False
        a.x = float(tx)
        if abs(a.y - ty) > 0.01:
            a.y = approach(a.y, ty, sp)
            return False
        a.y = float(ty)
        return True

    def stairs(self, a, f):
        if self.step_to(a, STAIR_X, CORR_Y):
            a.dest = (a.b, f)
            a.transit = max(1, int(STAIR_T * abs(f - a.floor) / a.walk))
            a.trip = None

    def get_wet(self, a):
        if a.wet:
            return
        if isinstance(a, Guest):
            a.wet = True
            self.d_wet += 1
        elif isinstance(a, Visitor) and a.booking is not None:
            a.wet = True
            a.booking.wet += 1

    def move(self, a):
        if a.transit > 0:
            a.transit -= 1
            if a.transit <= 0:
                outdoor = a.trip is not None
                a.b, a.floor = a.dest
                a.dest, a.trip = None, None
                if outdoor:
                    a.x, a.y = float(ENTRANCE_X), float(CORR_Y)
                else:
                    a.x, a.y = float(STAIR_X), float(CORR_Y)
            return False
        if a.goal is None:
            return False
        gb, gf, gx, gy = a.goal
        if a.b is not gb:
            if a.floor != 0:
                self.stairs(a, 0)
            elif self.step_to(a, ENTRANCE_X, CORR_Y):
                total = (OUT_BASE + OUT_PER_LOT * lot_dist(a.b.lot, gb.lot)) / a.walk
                cov = self.covered(a.b.lot, gb.lot)
                w = self.weather_at()
                if w == "SNOW" and not cov:
                    total *= SNOW_SLOW
                if w in ("RAIN", "SNOW") and not cov:
                    self.get_wet(a)
                total = int(total)
                a.trip = (a.b.lot, gb.lot, total)
                a.dest = (gb, 0)
                a.transit = total
            return False
        if a.floor != gf:
            self.stairs(a, gf)
            return False
        return self.step_to(a, gx, gy)

    def exit_goal(self, a):
        return (a.b or self.main, 0, ENTRANCE_X + 4, CORR_Y)

    def outdoor_walkers(self):
        return [a for a in self.guests + self.staff + self.visitors
                if a.transit > 0 and a.trip is not None and not a.hidden]

    # ---------------- guests ----------------
    def queue_pos(self, i):
        return (self.main, 0, min(SX0 + 32 + 7 * i, ENTRANCE_X - 6), CORR_Y + 4)

    def spawn_guest(self, gtype, kw):
        kw = dict(kw)
        want = kw.pop("want", None)
        couple = kw.pop("couple", False)
        vip = (self.star >= 2 and random.random() < 0.12 and kw.get("group") is None
               and not kw.get("celeb"))
        g = Guest(gtype, self.main, vip=vip, **kw)
        g.want = "SUITE" if vip else (want or self.pick_want(gtype))
        g.couple = couple
        g.goal = self.queue_pos(len(self.desk_queue))
        self.guests.append(g)

    def patience(self, g):
        return DESK_PATIENCE * g.spec["patience"] * (1.5 if g.group or g.celeb else 1.0)

    def room_pref(self, g, c):
        dist = lot_dist(c.b.lot, self.main.lot)
        if g.gtype == "TOURIST":
            return (0 if self.is_ocean(c) else 1, dist, c.f)
        return (0 if self.trait(c.b.lot) == "STATION" else 1, dist, c.f)

    # ---------------- upgrades (STEP 17) ----------------
    @staticmethod
    def upg_key(c):
        return "ROOM" if c.is_room() else c.kind

    def upgrade_info(self, c):
        """(next_spec, cost) or (None, 0) when maxed / not upgradable"""
        table = UPGRADES.get(self.upg_key(c))
        lv = getattr(c, "lv", 1)
        if not table or lv >= len(table):
            return None, 0
        nxt = table[lv]
        return nxt, int(round(c.spec["cost"] * nxt["rate"], -1))

    def upgrade_block(self, c):
        nxt, cost = self.upgrade_info(c)
        if nxt is None:
            return "最大レベル"
        if c.is_room() and c.guest is not None:
            return "宿泊客がいます"
        if self.star < 2:
            return "要★2"
        if self.cash < cost:
            return "資金不足"
        return ""

    def upgrade(self, c):
        why = self.upgrade_block(c)
        if why:
            self.log("改装できません：" + why)
            return False
        nxt, cost = self.upgrade_info(c)
        self.cash -= cost
        c.lv += 1
        self.log("%s（%s）：%s（-$%d）" % (c.label, c.number() if c.is_room() else
                                        c.b.name, nxt["label"], cost))
        return True

    def desk_upgrade_info(self):
        table = UPGRADES["FRONT"]
        if self.desk_lv >= len(table):
            return None, 0
        nxt = table[self.desk_lv]
        return nxt, nxt["cost"]

    def upgrade_desk(self):
        nxt, cost = self.desk_upgrade_info()
        if nxt is None or self.cash < cost or self.star < self.desk_lv + 1:
            self.log("フロントを強化できません")
            return False
        self.cash -= cost
        self.desk_lv += 1
        self.log("フロント：%sを導入しました（-$%d）" % (nxt["label"], cost))
        return True

    def update_kiosk(self):
        """STEP 17: the kiosk checks in business guests without staff"""
        if self.desk_lv < 2:
            return
        if self.kiosk_t > 0:
            self.kiosk_t -= 1
            return
        for x in self.desk_queue:
            if x.gtype == "BUSINESS" and x.group is None and not x.vip and not x.celeb:
                self.desk_queue.remove(x)
                x.kiosk = True
                x.state = "checkin"
                self.finish_checkin(x)
                self.kiosk_t = KIOSK_T
                return

    # ---------------- room holds (STEP 16) ----------------
    @staticmethod
    def hold_of(c):
        return getattr(c, "hold", None)

    def hold_for(self, g, c):
        """True if room c is held specially for guest g"""
        h = self.hold_of(c)
        if h is None:
            return False
        k, ref = h
        if k == "CELEB":
            return g.celeb
        if k == "BRIDE":
            return getattr(g, "couple", False) and g.group is ref
        if k == "GROUP":
            return g.group is ref and not getattr(g, "couple", False)
        return False

    def can_use(self, g, c):
        h = self.hold_of(c)
        if h is None:
            return True
        if h[0] == "PLAYER":
            return g.vip or g.celeb
        return self.hold_for(g, c)

    def tonight_free(self, c):
        """room can be given to someone tonight (empty, or its guest leaves today)"""
        if c.state == "broken":
            return False
        x = c.guest
        return x is None or x.checkout_t is not None or x.state in ("checkout", "leaving")

    def held_cells(self, kind=None, ref=None):
        out = []
        for c in self.rooms():
            h = self.hold_of(c)
            if h and (kind is None or h[0] == kind) and (ref is None or h[1] is ref):
                out.append(c)
        return out

    def hold(self, c, kind, ref=None):
        c.hold = (kind, ref)

    def unhold(self, c):
        c.hold = None

    def hold_rooms(self, ref, n, want, kind="GROUP"):
        """keep n rooms for a booking (prefer the wanted type, same floor)"""
        cands = [c for c in self.rooms() if self.hold_of(c) is None and self.tonight_free(c)
                 and c.kind != "SUITE"]
        cands.sort(key=lambda c: (c.kind != want, ROOM_TIER[c.kind] != ROOM_TIER[want],
                                  c.guest is not None, lot_dist(c.b.lot, self.main.lot),
                                  c.b.no, c.f, c.s))
        got = cands[:n]
        for c in got:
            self.hold(c, kind, ref)
        return got

    def celeb_suite(self):
        """(suite, guest_to_move) for a celebrity, or (None, None)"""
        suites = [c for c in self.rooms() if c.kind == "SUITE" and c.state != "broken"
                  and (self.hold_of(c) is None or self.hold_of(c)[0] == "PLAYER")]

        def score(c):
            return (-self.security(c.b), not self.is_ocean(c), -c.f)
        free = sorted([c for c in suites if self.tonight_free(c)], key=score)
        if free:
            return free[0], None
        for c in sorted(suites, key=score):
            x = c.guest
            if x is not None and self.move_target(x, c) is not None:
                return c, x
        return None, None

    def move_target(self, x, old):
        rooms = [c for c in self.rooms() if c is not old and c.state == "clean"
                 and c.guest is None and self.hold_of(c) is None]
        if not rooms:
            return None
        return min(rooms, key=lambda c: (-ROOM_TIER[c.kind], self.room_pref(x, c)))

    def move_guest(self, x, new):
        old = x.room
        old.guest = None
        old.state = "dirty"
        new.guest = x
        new.state = "occupied"
        x.room = new
        x.moved = True
        x.state = "to_room"
        x.goal = new.bed_pt()
        self.cash -= MOVE_COMP
        self.change_rep(-1.0)
        self.log("%s号室の客に%s号室へ移ってもらいました（-$%d）" % (
            old.number(), new.number(), MOVE_COMP))

    def toggle_player_hold(self, c):
        h = self.hold_of(c)
        if h is None:
            self.hold(c, "PLAYER")
            self.log("%s号室をVIP用に空けておきます" % c.number())
        elif h[0] == "PLAYER":
            self.unhold(c)
            self.log("%s号室のVIP用確保を解除しました" % c.number())

    def hold_label(self, c):
        h = self.hold_of(c)
        return HOLD_LABEL[h[0]] if h else ""

    def free_room(self, g):
        mine = [c for c in self.rooms() if c.state == "clean" and c.guest is None
                and self.hold_for(g, c)]
        if mine:                                   # STEP 16: the room kept for this guest
            c = mine[0]
            t, w = ROOM_TIER[c.kind], ROOM_TIER[g.want]
            how = "ok" if c.kind == g.want else ("swap" if t == w else
                                                  "upgrade" if t > w else "downgrade")
            return c, how
        rooms = [c for c in self.rooms() if c.state == "clean" and c.guest is None
                 and self.can_use(g, c)]
        if not rooms:
            return None, ""
        tier = ROOM_TIER[g.want]

        def best(cands):
            if g.celeb:
                return max(cands, key=lambda c: self.security(c.b))
            return min(cands, key=lambda c: self.room_pref(g, c))
        for cands, how in (
                ([c for c in rooms if c.kind == g.want], "ok"),
                ([c for c in rooms if c.kind != g.want and ROOM_TIER[c.kind] == tier], "swap"),
                ([c for c in rooms if ROOM_TIER[c.kind] > tier], "upgrade"),
                ([c for c in rooms if ROOM_TIER[c.kind] < tier], "downgrade")):
            if cands:
                if how == "upgrade":
                    t = min(ROOM_TIER[c.kind] for c in cands)
                    cands = [c for c in cands if ROOM_TIER[c.kind] == t]
                if how == "downgrade":
                    t = max(ROOM_TIER[c.kind] for c in cands)
                    cands = [c for c in cands if ROOM_TIER[c.kind] == t]
                return best(cands), how
        return None, ""

    def guest_leave(self, g, angry=False):
        g.state = "leaving"
        g.goal = self.exit_goal(g)
        if angry:
            g.angry = True

    def finish_checkin(self, g):
        room, how = self.free_room(g)
        if g.group is None and room is not None and self.sellable_rooms() <= bk.held_rooms(self):
            room = None                     # keep rooms for today's booked group
        if room is not None and g.group is not None and not self.hold_for(g, room):
            for c in self.held_cells("GROUP", g.group):   # took another room: free one hold
                if c.guest is None or c.state != "occupied":
                    self.unhold(c)
                    break
        if room is None and getattr(g, "couple", False):
            self.log("新郎新婦の部屋が用意できなかった…")
            self.guest_leave(g)
            return
        if room is None and g.group is not None:
            g.group.missed += 1
            self.log("団体客の部屋が足りない！")
            self.guest_leave(g)
            return
        if room is None:
            self.d_lost_full += 1                    # no rep loss: "fully booked"
            if any(k.kind in DINNER_KINDS and k.is_open() for k in self.food_cells()) \
                    and random.random() < DROPIN_P and self.t < LUNCH_T + 900:
                self.d_dropins += 1                  # STEP 18: stays for dinner anyway
            self.d_lost_value += self.prices.get(g.want, self.prices["SINGLE"])
            self.guest_leave(g)
            return
        room.guest = g
        room.state = "occupied"
        g.room = room
        g.how = how
        if how in self.d_how:
            self.d_how[how] += 1
        kind = g.want if how == "upgrade" else None
        g.paid = self.room_price(room, kind) * g.price_mult * g.nights
        self.cash += g.paid
        self.d_income += g.paid
        self.d_guests += 1
        self.d_types[g.gtype] += 1
        self.d_rooms_by[room.kind] += 1
        if g.vip or g.celeb:
            self.d_vips += 1
        if room.hold is not None and room.hold[0] != "PLAYER":
            self.unhold(room)                     # hold used up
        if getattr(g, "couple", False):
            g.group.couple_stay = True
            self.log("新郎新婦がスイートにチェックイン")
        elif g.group is not None:
            g.group.checked_in += 1
        g.state = "to_room"
        g.goal = room.bed_pt()

    def checkout_score(self, g, notes=None):
        notes = [] if notes is None else notes

        def note(d, text):
            notes.append((d, text))

        sc = 1.5
        if g.desk_wait > self.patience(g) * 0.6:
            note(-0.8, "フロントで長く待たされた")
        if g.vip:
            if g.room and g.room.kind == "SUITE":
                note(2.5, "スイートが素晴らしかった")
            else:
                note(-1.5, "VIPなのにスイートでなかった")
        if g.how == "swap":
            note(-0.3, "希望と違うタイプの部屋だった")
        elif g.how == "upgrade":
            note(1.0, "無料で良い部屋にしてもらえた")
        elif g.how == "downgrade":
            note(-0.8, "希望より狭い部屋だった")
        w = g.spec["food_w"]
        if g.sick:
            note(-4.0, "食事で体調を崩した…")
        elif g.meals:
            if g.pref in g.meals:
                note(1.0 * w, "好きな料理が食べられた")
            else:
                note(0.4 * w, "食事がおいしかった")
        elif getattr(g, "hungry", False):
            note(-0.4 * w, "レストランが満席だった")
        elif self.star >= 2 and not self.food_cells():
            note(-0.3 * w, "ホテルで食事できなかった")
        if g.room is not None:
            if self.is_ocean(g.room):
                note(OCEAN_SAT[g.gtype], "部屋から海が見えた")
            gb = self.garden_bonus(g.room.b)
            if gb:
                note(gb, "庭園がきれいだった")
            if g.how != "upgrade" and 0 < g.price_mult <= 1.0:
                k = g.room.kind
                over = (self.prices[k] - self.fair(k)) / self.fair(k)
                if over > 0:
                    note(-over * (2.0 if k == "SUITE" else 1.0), "料金が高すぎる")
                elif over < -0.15:
                    note(0.3, "お手頃な料金だった")
        if g.wet:
            note(WET_SAT, "雨の中を歩かされた")
        if getattr(g, "moved", False):
            note(-0.6, "途中で部屋を移らされた")
        if getattr(g, "couple", False):
            note(2.0, "ブライダルスイートで最高の一夜")
        if g.robbed:
            note(-3.0, "部屋で盗難にあった…")
        if g.room is not None and getattr(g.room, "lv", 1) >= 2:      # STEP 17
            note(ROOM_LV_SAT[g.room.lv], "高級家具で快適だった" if g.room.lv >= 3
                 else "内装がきれいだった")
        if getattr(g, "concierge", False):
            note(CONCIERGE_SAT, "コンシェルジュの案内が丁寧だった")
        rs.resort_score(self, g, note)
        ls.leisure_score(self, g, note)                                    # STEP 20
        if any(getattr(c, "tenant", None) for c in sh.tenant_cells(self)):   # STEP 19
            if g.vip or g.celeb:
                note(TENANT_SAT["VIP"], "ハイブランド店で買い物を楽しんだ")
            elif g.gtype == "TOURIST":
                note(TENANT_SAT["TOURIST"], "館内のお店が充実していた")
        return sc + sum(d for d, _ in notes)

    def change_rep(self, d):
        d = d * 0.5 * (1 - self.rep / 110) if d > 0 else d * 0.6
        self.rep = clamp(self.rep + d, 0, 100)

    def update_guest(self, g):
        if g.state == "enter":
            if self.move(g):
                if self.desk_lv >= 3 and (g.vip or g.celeb or g.group is not None):
                    g.concierge = True                  # STEP 17: no queue
                    g.state = "checkin"
                    self.finish_checkin(g)
                    return
                g.state = "queue_desk"
                if g.group is not None or g.celeb:      # booked guests: priority line
                    i = 0
                    while (i < len(self.desk_queue) and
                           (self.desk_queue[i].group is not None or self.desk_queue[i].celeb)):
                        i += 1
                    self.desk_queue.insert(i, g)
                else:
                    self.desk_queue.append(g)
        elif g.state == "queue_desk":
            g.desk_wait += 1
            g.goal = self.queue_pos(self.desk_queue.index(g))
            self.move(g)
            if g.desk_wait > self.patience(g):
                self.desk_queue.remove(g)
                self.d_lost_angry += 1
                if g.group is not None:
                    g.group.missed += 1
                if self.d_angry_pen < ANGRY_REP_CAP:
                    before = self.rep
                    self.change_rep(-2.0)
                    self.d_angry_pen += before - self.rep
                self.log("フロントが遅く、客が帰ってしまった")
                self.guest_leave(g, True)
        elif g.state == "to_room":
            if self.move(g):
                g.state = "in_room"
        elif g.state == "in_room":
            if g.checkout_t is not None and self.t >= g.checkout_t:
                g.state = "checkout"
                g.room.guest = None
                g.room.state = "dirty"
                g.goal = self.exit_goal(g)
        elif g.state == "checkout":
            if self.move(g):
                notes = []
                score = self.checkout_score(g, notes)
                rs.add_review(self, g, score, notes)
                self.change_rep(score)
                g.state = "gone"
        elif g.state == "leaving":
            if self.move(g):
                g.state = "gone"

    def update_visitor(self, v):
        if v.state == "enter":
            if self.move(v):
                v.state = "stay"
        elif v.state == "stay":
            if self.t >= v.leave_t or not self.exists(v.cell):
                v.state = "leave"
                v.goal = self.exit_goal(v)
        elif v.state == "leave":
            if self.move(v):
                v.state = "gone"

    # ---------------- food ----------------
    # ---------------- outside diners (STEP 18) ----------------
    def outside_mult(self, meal, day=None):
        d = self.day if day is None else day
        wd = self.weekday(d)
        m = (0.5 + self.rep / 100.0) * (1 + 0.15 * (self.star - 1))
        if meal == "lunch":
            m *= 1.2 if wd in ("MON", "TUE", "WED", "THU", "FRI") else 0.9
            if any(self.trait(l) == "STATION" for l in self.lots):
                m *= 1.2                              # office workers from the station
        else:
            m *= 1.3 if wd in ("FRI", "SAT") else 1.0
        m *= {"RAIN": 0.8, "SNOW": 0.7}.get(self.weather_at(d), 1.0)
        return m * self.parking_mult() * self.diff["demand"]

    def outside_expect(self, c, meal):
        if meal == "lunch" and not getattr(c, "lunch", False):
            return 0.0
        base = OUTSIDE.get(c.kind, (0, 0))[0 if meal == "lunch" else 1]
        return base * self.outside_mult(meal)

    def plan_outside(self):
        for c in self.food_cells():
            plan = {}
            for meal in ("lunch", "dinner"):
                e = self.outside_expect(c, meal)
                n = max(0, int(round(random.gauss(e, max(0.6, e * 0.3))))) if e > 0 else 0
                plan[meal] = n
                if n:
                    t = (LUNCH_T if meal == "lunch" else c.spec["serve"]) - 90
                    for i in range(min(n, 8)):              # visible guests (max 8)
                        self.add_timer(t + random.randint(0, 50) if t > 0 else 1,
                                       lambda c=c, i=i, t=t: self.add_out_visitor(c, i, t))
            c.out_plan = plan

    def add_out_visitor(self, c, i, t):
        if not self.exists(c) or not c.is_open():
            return
        span = 16 * c.w
        seat = (c.cx - span + (i % 4) * (2 * span // 3), c.depth_y(30 + (i // 4) * 18))
        entry = c.b if c.b.kind == "MALL" else self.main
        self.visitors.append(Visitor(entry, c, seat, t + 260 + random.randint(0, 40),
                                     OUTSIDE_COLOR))

    def toggle_lunch(self, c):
        if "lunch_price" not in c.spec:
            return False
        c.lunch = not c.lunch
        self.log("%s：ランチ営業を%sしました" % (c.label, "開始" if c.lunch else "やめに"))
        return True

    def cook_busy(self, st, early=0):
        if st.role != "COOK" or not st.post or st.post[0] != "FAC":
            return False
        c = st.post[1]
        times = ([c.spec["serve"]] if "serve" in c.spec else []) + bk.extra_serves(self, c)
        if getattr(c, "lunch", False):
            times.append(LUNCH_T)
        return any(s - COOK_PREP - early <= self.t < s + 50 for s in times)

    def dirt_mult(self):
        return 2.0 if self.cheap_food_days > 0 else 1.0

    def deep_clean(self, c):
        if self.cash < DEEP_CLEAN_COST:
            self.log("資金が足りません")
            return False
        self.cash -= DEEP_CLEAN_COST
        c.hygiene = 100.0
        self.log("%sを徹底清掃しました（-$%d）" % (c.label, DEEP_CLEAN_COST))
        return True

    def ready_cooks(self, c):
        return [st for st in self.staff
                if st.post == ("FAC", c) and st.role == "COOK" and st.state == "post"
                and st.b is c.b and st.floor == c.f and st.transit <= 0]

    def eat_chance(self, g, c):
        p = 0.45 * g.spec["food_w"]
        if g.pref == c.kind:
            p *= 2.0
        if self.food_boom and self.food_boom[0] == c.kind:
            p *= 1.5
        if c.kind == "ITALIAN" and g.want == "DOUBLE":          # STEP 18: couples
            p *= 1.8
        if c.kind == "FRENCH" and (g.vip or g.celeb):
            p *= 2.5
        if c.kind == "CHINESE" and (g.group is not None or g.price_mult < 1.0):
            p *= 1.8
        return min(0.95, p)

    def serve(self, c, meal="dinner"):
        spec = c.spec
        if not c.is_open():
            return
        cooks = self.ready_cooks(c)
        if not cooks:
            if any(st.post == ("FAC", c) and st.role == "COOK" for st in self.staff):
                self.log("%s：料理人が間に合わない！" % c.label)
            return
        cap = sum(int(spec["per_cook"] * min(1.0, st.speed())) for st in cooks)
        for st in cooks:
            st.fatigue = clamp(st.fatigue + 12, 0, 100)
            st.exp += 400
        guests = [g for g in self.guests if g.state == "in_room" and not g.sick]
        rate = 0.35 if meal == "lunch" else 1.0
        diners = [g for g in guests if random.random() < self.eat_chance(g, c) * rate]
        diners.sort(key=lambda g: g.pref != c.kind)
        for x in diners[cap:]:
            if not x.meals and meal == "dinner":
                x.hungry = True
                self.d_hungry += 1
        diners = diners[:cap]
        # STEP 18: outside diners use the seats that are left
        out = c.out_plan.get(meal, 0)
        if meal == "dinner" and self.d_dropins and c.kind in DINNER_KINDS:
            out += self.d_dropins
            self.d_dropins = 0
        out = max(0, min(out, cap - len(diners)))
        n = len(diners) + out
        if n == 0:
            return
        for g in diners:
            g.meals.add(c.kind)
        price = spec.get("lunch_price", spec["price"]) if meal == "lunch" else spec["price"]
        mult = 1.3 if self.cheap_food_days > 0 else 1.0
        rev = int(n * price * mult)
        if out:
            self.d_out[meal] += out
            self.d_out_food += int(out * price * mult)
        self.cash += rev
        self.d_income += rev
        self.d_food += rev
        self.d_meals[c.kind] += n
        c.served_today += n
        self.log("%s：%s %d食%s +$%d" % (c.label, "ランチ" if meal == "lunch" else spec["meal"],
                                          n, "（外来%d）" % out if out else "", rev))
        h = c.hygiene
        c.hygiene = max(0.0, c.hygiene - spec["dirt"] * n * self.dirt_mult())
        if h < HYGIENE_DANGER:
            p = POISON_MAX_P * (HYGIENE_DANGER - h) / HYGIENE_DANGER
            if random.random() < p:
                self.food_poisoning(c, diners, n)

    def food_poisoning(self, c, diners, total=0):
        n_sick = max(1, (total or len(diners)) // 3)
        for g in random.sample(diners, min(len(diners), n_sick)):
            g.sick = True
        c.closed_days = POISON_CLOSE_DAYS
        self.cash -= POISON_COMP * n_sick
        self.rep = clamp(self.rep - POISON_REP, 0, 100)
        self.d_poison += n_sick
        self.log("%sで食中毒が発生！" % c.label)
        popup = poisoning_popup(self, c, n_sick)
        self.events.note(self, popup)
        self.pending.append(popup)

    # ---------------- staff ----------------
    def at_post(self, st):
        gb, gf, gx, gy = self.post_pos(st)
        return (st.b is gb and st.floor == gf and st.transit <= 0
                and st.x == gx and st.y == gy)

    def update_staff(self, st):
        if st.post is None:
            st.fatigue = max(0, st.fatigue - 0.05)
            return
        working = False
        if st.state in ("go_post", "go_rest", "go_room"):
            if self.move(st):
                if st.state == "go_post":
                    st.state = "post"
                elif st.state == "go_rest":
                    st.state = "rest"
                else:
                    st.state = "work"
                    st.timer = CLEAN_T * st.task.spec["clean_mult"]
        elif st.state == "rest":
            st.fatigue -= 0.25
            if st.fatigue <= 15 or self.cook_busy(st):
                self.release(st)
                st.state = "go_post"
                st.goal = self.post_pos(st)
        elif st.state == "post":
            if st.fatigue >= self.break_rule() and not self.cook_busy(st, 300):
                if self.send_rest(st):
                    return
            if st.role == "FRONT":
                if self.desk_queue and self.at_post(st):
                    g = self.desk_queue.pop(0)
                    g.state = "checkin"
                    g.goal = None
                    g.x, g.y = st.x, float(CORR_TOP + 4)
                    st.task = g
                    st.state = "work"
                    st.timer = CHECKIN_T
            elif st.role == "CLEANER" and st.post[0] == "FLOOR":
                b, f = st.post[1], st.post[2]
                cells = sorted(self.floor_cells(b, f),            # STEP 16: held rooms first
                               key=lambda c: self.hold_of(c) is None)
                for c in cells:
                    if c.is_room() and c.state == "dirty" and c.claimed is None:
                        c.claimed = st
                        st.task = c
                        st.state = "go_room"
                        st.goal = c.work_pt()
                        break
            elif st.role == "CLEANER" and st.post[0] == "FAC":
                c = st.post[1]
                if self.at_post(st) and c.hygiene < 97:
                    st.task = c
                    st.state = "work"
                    st.timer = FAC_CLEAN_T
            elif st.role == "GUARD" and st.post[0] == "PATROL":
                if self.at_post(st):
                    st.wait += 1
                    if st.wait >= PATROL_WAIT:
                        st.wait = 0
                        st.patrol = self.new_patrol_point(st)
                st.fatigue += 0.002
            if st.state == "post":
                st.goal = self.post_pos(st)
                self.move(st)
        elif st.state == "work":
            working = True
            st.timer -= st.speed()
            st.exp += 1
            if st.timer <= 0:
                if st.role == "FRONT":
                    g = st.task
                    st.task = None
                    self.finish_checkin(g)
                elif st.role == "CLEANER":
                    c = st.task
                    st.task = None
                    if c.has_hygiene():
                        c.hygiene = min(100.0, c.hygiene + FAC_CLEAN_GAIN)
                    else:
                        if c.state == "dirty":
                            c.state = "clean"
                        c.claimed = None
                st.state = "post"
        if working:
            st.fatigue += 0.03
        elif st.state != "rest":
            st.fatigue += 0.006
        st.fatigue = clamp(st.fatigue, 0, 100)
        if st.skill < 3 and st.exp >= EXP_LV[st.skill - 1]:
            st.skill += 1
            self.log("%sの腕が上がった！（%s）" % (st.name, st.stars()))

    # ---------------- day end / day start ----------------
    def upkeep(self):
        cheap = self.cheap_food_days > 0
        u = sum(0 if (cheap and c.is_food()) else c.spec["upkeep"] for c in self.cells())
        u += sum(LOT_FACILITIES[k]["upkeep"] for k in self.lot_fac.values())
        u += (KIOSK_UPKEEP if self.desk_lv >= 2 else 0) + \
            (CONCIERGE_UPKEEP if self.desk_lv >= 3 else 0)
        u += CAMERA_UPKEEP * sum(len(b.cams) for b in self.buildings)
        return u + sum(b.spec["upkeep"] for b in self.buildings)

    def end_of_day(self):
        self.close_day()
        self.take_snapshot()        # SAVE point = this morning
        self.begin_day()

    def close_day(self):
        self.d_gym = ls.gym_day(self)                # STEP 20: member fees
        rent_today, bonus_today, tenant_pops = sh.tenants_night(self, self.d_vips)
        self.cash += rent_today + bonus_today
        self.d_income += rent_today + bonus_today
        for pp in tenant_pops:
            self.events.note(self, pp)
            self.pending.append(pp)
        wages = sum(s.wage() for s in self.staff)
        upkeep = self.upkeep()
        interest = int(self.debt * self.interest_rate() + 0.999) if self.debt > 0 else 0
        self.cash -= wages + upkeep + interest
        overdraft = 0
        if self.cash < 0:
            overdraft = int(-self.cash) + 100
            self.debt += overdraft
            self.cash += overdraft - 100
            self.log("資金不足！銀行が$%dを貸付（手数料$100）" % (overdraft - 100))
        if self.debt > self.credit_limit():
            self.over_limit_nights += 1
            if self.over_limit_nights >= 3:
                self.bankrupt = True
        else:
            self.over_limit_nights = 0
        quits = []
        for st in list(self.staff):
            if st.fatigue >= 95 and random.random() < 0.3:
                quits.append(st.name)
                self.unassign(st)
                self.staff.remove(st)
        for st in self.staff:
            st.fatigue = max(0, st.fatigue - 20)
        for b in bk.today_bookings(self):
            self.pending.append(bk.evaluate(self, b))
        self.visitors = []
        self.timers = []
        for g in self.guests:
            if g.state in ("in_room", "to_room"):
                g.nights -= 1
                g.bath = None
                g.spa = False if g.nights > 0 else g.spa
                if g.nights <= 0:
                    g.checkout_t = random.randint(*CHECKOUT_RANGE)
        self.guests = [g for g in self.guests if g.state != "gone"]
        for c in self.rooms():
            if c.hold is not None and c.hold[0] != "PLAYER":      # STEP 16
                c.hold = None
            if c.state == "broken" and c.broken_days < 99:
                c.broken_days -= 1
                if c.broken_days <= 0:
                    c.state = "dirty"
                    self.log("%s号室が再開（要清掃）" % c.number())
        hyg = []
        for c in self.hygiene_cells():
            c.hygiene = max(0.0, c.hygiene - HYGIENE_DAILY_DROP * self.dirt_mult())
            hyg.append((c.label, int(c.hygiene), c.closed_days))
            if c.closed_days > 0:
                c.closed_days -= 1
                if c.closed_days == 0:
                    self.log("%sが営業再開" % c.label)
        if self.cheap_food_days > 0:
            self.cheap_food_days -= 1
            if self.cheap_food_days == 0:
                self.log("格安業者との契約が終了")
        if self.bridal_boom > 0:
            self.bridal_boom -= 1
        if self.crime_wave > 0:
            self.crime_wave -= 1
        if self.food_boom:
            k, d = self.food_boom
            self.food_boom = (k, d - 1) if d > 1 else None
        self.report = {
            "day": self.day, "weekday_label": self.weekday_label(),
            "season_label": self.season_label(), "rokuyo": self.rokuyo(),
            "month": self.month(),
            "income": self.d_income, "food": self.d_food, "meals": dict(self.d_meals),
            "poison": self.d_poison, "hygiene": hyg,
            "wages": wages, "upkeep": upkeep, "interest": interest,
            "overdraft": max(0, overdraft - 100), "guests": self.d_guests,
            "types": dict(self.d_types),
            "full": self.d_lost_full, "angry_desk": self.d_lost_angry,
            "lost_value": self.d_lost_value, "lost_busy": self.d_lost_busy,
            "out": dict(self.d_out), "out_food": self.d_out_food,
            "shop": self.d_shop, "umbrella": self.d_umbrella,
            "leisure": self.d_leisure, "pool_out": self.d_pool_out, "gym": self.d_gym,
            "gym_members": int(self.gym_members),
            "rent": rent_today, "rent_bonus": bonus_today, "vips": self.d_vips,
            "hungry": self.d_hungry,
            "rep0": self.d_rep0, "rep1": self.rep, "quits": quits,
            "over": self.over_limit_nights,
            "rental": self.d_rental, "bookings": list(self.d_booking),
            "weather": self.weather_at(), "wet": self.d_wet, "how": dict(self.d_how),
            "rooms_by": dict(self.d_rooms_by), "sec": dict(self.d_sec),
            "resort": self.d_resort, "reviews": list(self.d_reviews),
            "review_avg": rs.review_avg(self) if self.reviews else None,
            "rival": dict(self.rival) if self.rival else None,
        }
        self.check_star()
        old_season, old_month = self.season(), self.month()
        self.day += 1
        self.t = 0
        self.forecast(self.day)
        if self.season() != old_season:
            self.log("%sがやってきた！" % self.season_label())
        if self.month() != old_month and self.month() == 6:
            self.log("6月：ジューンブライドの季節！挙式の依頼が増えます")
        dm = self.demand_mult()
        self.report["next_label"] = (self.weekday_label(), self.season_label(),
                                     "+++" if dm >= 1.3 else "++" if dm >= 1.1 else
                                     "+" if dm >= 0.9 else "-")
        self.reset_daily()
        self.new_candidates()
        self.plan_arrivals()

    def begin_day(self):
        """morning: things that create timers / choice popups (not in the snapshot)"""
        bk.start_day(self)
        self.plan_outside()
        sh.plan_shoppers(self)
        ls.plan_pool(self)
        offer = sh.tenant_offer(self)
        if offer:
            self.pending.append(offer)
        sec.plan_incidents(self)
        rs.rival_day(self)
        if self.rival is None and self.day >= RIVAL_DAY and self.star >= 2:
            rs.open_rival(self)
            popup = {"title": "!! ライバルホテル開業 !!",
                     "lines": ["近くに「%s」がオープンしました！" % self.rival["name"],
                               "評判 %d。お客の取り合いになります。" % self.rival["rep"],
                               "相手より評判が高いほど、客が増えます。",
                               "（評判の比較はカレンダー C で確認）"],
                     "choices": [("受けて立つ！", True, None)]}
            self.events.note(self, popup)
            self.pending.append(popup)
        for offer in bk.roll_offers(self):
            self.pending.append(offer)
        popup = self.events.roll(self)
        if popup:
            self.pending.append(popup)

    def star_ok(self, nxt):
        rooms_n, extra, rep, _ = STAR_GOALS[nxt]
        if len(self.rooms()) < rooms_n or self.rep < rep:
            return False
        if extra == "dinner":
            return any(s.role == "COOK" and s.post and s.post[0] == "FAC"
                       and s.post[1].kind in DINNER_KINDS for s in self.staff)
        return True

    def check_star(self):
        nxt = self.star + 1
        if nxt in STAR_GOALS and self.star_ok(nxt):
            self.star = nxt
            self.log("★%dに昇格しました！ 適正価格が上がりました" % self.star)
            self.report["star_up"] = self.star
            self.report["fair_up"] = self.fair("SINGLE")
        elif nxt == 4 and not self.free_play:
            for key in ROUTE_ORDER:
                if rs.route_done(self, key):
                    self.star = 4
                    self.route = key
                    self.cleared = True
                    self.log("★4達成！「%s」として完成！" % ROUTES[key]["label"])
                    self.report["star_up"] = 4
                    break

    def keep_playing(self):
        self.cleared = False
        self.free_play = True
        self.log("引き続き経営を楽しみましょう！")

    # ---------------- main tick ----------------
    def tick(self):
        if self.cleared or self.bankrupt or self.pending:
            return
        limit = QUEUE_BASE + QUEUE_PER_FRONT * max(1, self.post_count(("DESK",)))
        while self.arrivals and self.arrivals[0][0] <= self.t:
            _, gt, kw = self.arrivals.pop(0)
            if (kw.get("group") is None and not kw.get("celeb")
                    and len(self.desk_queue) >= limit):
                if self.t + QUEUE_RETRY < DAY_TICKS - 200:
                    self.add_arrival(self.t + QUEUE_RETRY, gt, **kw)   # come back later
                else:
                    self.d_lost_busy += 1
                continue
            self.spawn_guest(gt, kw)
        for g in self.guests:
            if g.state != "checkin":
                self.update_guest(g)
        for st in self.staff:
            self.update_staff(st)
        self.update_kiosk()
        for v in self.visitors:
            self.update_visitor(v)
        if self.t % 2 == 0:
            sh.passing_trade(self)                   # STEP 19
        while self.timers and self.timers[0][0] <= self.t:
            _, fn = self.timers.pop(0)
            fn()
            if self.pending:
                break
        for c in self.food_cells():
            if self.t == c.spec["serve"]:
                self.serve(c)
            elif self.t == LUNCH_T and getattr(c, "lunch", False):
                self.serve(c, "lunch")
        if self.t == BATH_T:
            rs.bath_time(self)
        if self.t == POOL_T:
            ls.pool_time(self)                       # STEP 20
        elif self.t == NIGHT_POOL_T:
            ls.pool_time(self, night=True)
        self.t += 1
        if self.t >= DAY_TICKS:
            self.end_of_day()

    def net_worth(self):
        assets = sum(c.spec["cost"] * 0.5 for c in self.cells())
        assets += sum(b.spec["cost"] * 0.5 for b in self.buildings)
        assets += sum(self.land_price(l) * 0.5 for l in self.lots if l not in START_LOTS)
        assets += sum(LOT_FACILITIES[k]["cost"] * 0.5 for k in self.lot_fac.values())
        return int(self.cash - self.debt + assets)


_ = (PRICE_STEP, CAMERA_COST)
