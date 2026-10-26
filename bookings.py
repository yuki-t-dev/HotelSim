# ============================================================
# bookings.py  -  reservations
#   CONF    : meeting rooms + group rooms (+ banquet) (+ guards for VIPs)
#   PARTY   : banquet
#   WEDDING : ceremony (chapel / shrine) -> reception (banquet hall)
#             + dress room (+ overnight guests).  June = June bride!
#   YUINO   : betrothal meeting in the yuino room. success -> wedding offer
# ============================================================
import random

from data import (FACILITIES, OFFER_CHANCE, OFFER_LEAD, MAX_BOOKINGS,
                  MEET_ARRIVE, MEET_T, MEET_END, GROUP_ARRIVE, PARTY_ARRIVE, PARTY_END,
                  RENTAL_PRICE, RENTAL_END, COMPANIES, CONF_NAMES, PARTY_NAMES, SEASON_PARTY,
                  FAMILIES, FAMILY_PARTY, ROKUYO_WED, ROKUYO_PAY, WED_CHANCE, WED_SEASON,
                  WED_LEAD, WED_ARRIVE, CEREMONY_T, TO_RECEPTION_T, RECEPTION_T, WED_END,
                  WED_STAY_ARRIVE, YUINO_ARRIVE, YUINO_T, YUINO_END, GARDEN_WED_BONUS,
                  JUNE_DAY_WEIGHT, JUNE_OFFER, JUNE_PAY,
                  WED_OFFER_P, YUINO_OFFER_P, CEREMONY_ONLY_PAY,
                  VIP_CONF_CHANCE, VIP_CONF_GUARDS, VIP_CONF_PAY,
                  HYGIENE_DANGER, POISON_MAX_P, POISON_CLOSE_DAYS, POISON_REP, POISON_COMP,
                  COUPLE_REP,
                  clamp, t_to_clock)
from model import Visitor
from events import poisoning_popup

BANQ = FACILITIES["BANQUET"]
KIND_SHORT = {"CONF": "会議", "PARTY": "宴会", "WEDDING": "挙式", "YUINO": "結納"}


class Booking:
    def __init__(self, kind, day, title, people, pay, penalty, meet=0, banquet=False,
                 rooms=0, style=None, family=None, guards=0):
        self.kind = kind
        self.day = day
        self.title = title
        self.people = people
        self.pay = pay
        self.penalty = penalty
        self.meet = meet
        self.banquet = banquet
        self.rooms = rooms
        self.style = style
        self.family = family
        self.guards = guards
        self.status = "booked"
        self.meet_ok = None
        self.guard_ok = None
        self.ceremony_ok = None
        self.dress_ok = None
        self.served = None
        self.poison = False
        self.gift = None
        self.checked_in = 0
        self.missed = 0
        self.wet = 0
        self.rooms_used = []
        self.cells_used = []
        self.couple_stay = False    # STEP 16

    def short(self):
        return KIND_SHORT[self.kind]

    def venue_label(self):
        return "チャペル" if self.style == "CHAPEL" else "神殿"


def meeting_rooms(g):
    return [c for c in g.cells(("MEETING",)) if c.is_open()]


def one(g, kind):
    cs = list(g.cells((kind,)))
    return cs[0] if cs else None


def banquet_hall(g):
    return one(g, "BANQUET")


def venue_cell(g, style):
    return g.chapel_hall() if style == "CHAPEL" else one(g, "SHRINE")


def banquet_capacity(g, ready_only=False):
    hall = banquet_hall(g)
    if hall is None:
        return 0
    cooks = g.ready_cooks(hall) if ready_only else [
        st for st in g.staff if st.post == ("FAC", hall) and st.role == "COOK"]
    return sum(int(BANQ["per_cook"] * min(1.0, st.speed())) for st in cooks)


def requirements(g, b):
    out = []
    if b.kind == "WEDDING":
        v = venue_cell(g, b.style)
        out.append(("%s（挙式 %s）" % (b.venue_label(), t_to_clock(CEREMONY_T)), v is not None))
        out.append(("衣装室（花嫁の支度）", one(g, "DRESS") is not None))
    if b.kind == "YUINO":
        out.append(("結納の間", one(g, "YUINO") is not None))
    if b.meet:
        n = len(meeting_rooms(g))
        out.append(("会議室 %d室（今%d室）" % (b.meet, n), n >= b.meet))
    if b.guards:
        n = g.guard_count()
        out.append(("警備員 %d人を配置（今%d人）" % (b.guards, n), n >= b.guards))
    if b.banquet:
        if banquet_hall(g) is None:
            out.append(("宴会場（未建設）", False))
        else:
            cap = banquet_capacity(g)
            when = t_to_clock(RECEPTION_T if b.kind == "WEDDING" else BANQ["serve"])
            out.append(("宴会料理 %d食 %s（今%d食分）" % (b.people, when, cap), cap >= b.people))
    if b.rooms:
        n = len(g.rooms())
        out.append(("客室 %d室を確保（全%d室）" % (b.rooms, n), n >= b.rooms + 2))
    return out


def open_bookings(g):
    return sorted([b for b in g.bookings if b.status == "booked"], key=lambda b: b.day)


def today_bookings(g):
    return [b for b in g.bookings if b.status == "booked" and b.day == g.day]


# STEP 13: two independent lines -> a wedding and a meeting can share a day
CATEGORY = {"WEDDING": "wed", "YUINO": "wed", "CONF": "biz", "PARTY": "biz"}


def bookings_on(g, day):
    return [b for b in g.bookings if b.status == "booked" and b.day == day]


def booking_on(g, day, cat=None):
    for b in bookings_on(g, day):
        if cat is None or CATEGORY[b.kind] == cat:
            return b
    return None


def banquet_busy(g, day):
    """the banquet hall is already used that day"""
    return any(b.banquet for b in bookings_on(g, day))


def held_rooms(g):
    """group rooms still needed today that are NOT covered by a room hold"""
    out = 0
    for b in today_bookings(g):
        need = max(0, b.rooms - b.checked_in - b.missed)
        out += max(0, need - len(g.held_cells("GROUP", b)))
    return out


def cell_in_use(g, c):
    for b in today_bookings(g):
        if c in b.rooms_used or c in b.cells_used:
            return True
        if b.banquet and c.kind == "BANQUET":
            return True
    return False


def extra_serves(g, c):
    if c.kind != "BANQUET":
        return []
    return [RECEPTION_T for b in today_bookings(g) if b.kind == "WEDDING" and b.banquet]


def seat_pt(c, i):
    k = c.kind
    if k == "MEETING":
        side = -9 if i % 2 == 0 else 9
        return (c.cx + side, c.depth_y(26 + (i // 2 % 5) * 9))
    if k == "CHAPEL_HALL":
        side = -1 if i % 2 == 0 else 1
        col = (i // 2) % 5
        row = (i // 10) % 4
        return (c.cx + side * (20 + col * 10), c.depth_y(22 + row * 10))
    if k == "SHRINE":
        side = -1 if i % 2 == 0 else 1
        return (c.cx + side * (18 + (i // 2) % 5 * 10), c.depth_y(28 + (i // 10) % 3 * 9))
    if k == "YUINO":
        pts = [(-14, 40), (14, 40), (-14, 52), (14, 52), (-14, 28), (14, 28), (0, 60), (0, 22)]
        dx, d = pts[i % len(pts)]
        return (c.cx + dx, c.depth_y(d))
    if k == "DRESS":
        return (c.cx - 8, c.depth_y(50))
    t = (i // 4) % 6
    tx = c.cx + (-46, 0, 46)[t % 3]
    ty = c.depth_y((30, 56)[t // 3])
    dx, dy = ((-6, 0), (6, 0), (0, -5), (0, 5))[i % 4]
    return (tx + dx, ty + dy)


def altar_pt(c, who):
    dx = -5 if who == "GROOM" else 5
    return (c.cx + dx, c.depth_y(64 if c.kind == "CHAPEL_HALL" else 60))


def add_visitors(g, cell, n, arrive, leave, color, booking=None):
    for i in range(n):
        t = arrive + random.randint(0, 40)
        g.add_timer(t, lambda c=cell, i=i: g.visitors.append(
            Visitor(g.main, c, seat_pt(c, i), leave + random.randint(0, 30), color, booking)))


# ------------------------------------------------------------
# offers
# ------------------------------------------------------------
def free_days(g, lead, cat):
    return [g.day + d for d in range(lead[0], lead[1] + 1)
            if booking_on(g, g.day + d, cat) is None]


def make_conf_or_party(g):
    days = free_days(g, OFFER_LEAD, "biz")
    if not days:
        return None
    day = random.choice(days)
    hall_free = not banquet_busy(g, day)
    if hall_free and random.random() < (0.35 if banquet_hall(g) else 0.2):
        people = random.randint(10, 22)
        name = random.choice(PARTY_NAMES + [SEASON_PARTY[g.season(day)]] * 2)
        if name in FAMILY_PARTY:
            title = "%s家 %s" % (random.choice(FAMILIES), name)
        else:
            title = "%s %s" % (random.choice(COMPANIES), name)
        pay = int(round(people * 36, -1))
        return Booking("PARTY", day, title, people, pay, int(pay * 0.3), banquet=True)
    max_rooms = max(3, min(10, len(g.rooms()) // 2 + 1))
    rooms = random.randint(3, max_rooms)
    people = rooms + random.randint(2, 8)
    meet = 1 if people <= 12 else 2
    banquet = hall_free and random.random() < 0.55
    vip = random.random() < VIP_CONF_CHANCE
    title = "%s %s" % (random.choice(COMPANIES), random.choice(CONF_NAMES))
    pay = rooms * g.fair("SINGLE") * 1.3 + 150 * meet + (30 * people if banquet else 0)
    if vip:
        pay *= VIP_CONF_PAY
    pay = int(round(pay, -1))
    return Booking("CONF", day, title, people, pay, int(pay * 0.4), meet=meet,
                   banquet=banquet, rooms=rooms, guards=VIP_CONF_GUARDS if vip else 0)


def wedding_day_weight(g, d):
    w = ROKUYO_WED[g.rokuyo(d)] * (1.5 if g.weekday(d) in ("SAT", "SUN") else 1.0)
    if g.month(d) == 6:
        w *= JUNE_DAY_WEIGHT
    return w


def pick_wedding_day(g):
    days = free_days(g, WED_LEAD, "wed")
    if not days:
        return None
    return random.choices(days, weights=[wedding_day_weight(g, d) for d in days])[0]


def june_near(g):
    return any(g.month(g.day + d) == 6 for d in range(WED_LEAD[0], WED_LEAD[1] + 1))


def make_wedding(g, family=None, bonus=1.0):
    day = pick_wedding_day(g)
    if day is None:
        return None
    styles = []
    if g.chapel_hall() is not None:
        styles.append("CHAPEL")
    if one(g, "SHRINE") is not None:
        styles.append("SHRINE")
    if not styles or random.random() < 0.25:
        styles = ["CHAPEL", "SHRINE"]
    style = random.choice(styles)
    fam = family or random.sample(FAMILIES, 2)
    people = random.randint(16, 24) if style == "CHAPEL" else random.randint(12, 20)
    rooms = random.randint(0, min(6, max(0, len(g.rooms()) // 3)))
    banquet = banquet_hall(g) is not None and not banquet_busy(g, day)
    pay = people * 55 + (600 if style == "CHAPEL" else 800) + rooms * g.fair("TWIN")
    if not banquet:                      # STEP 13: "ceremony only" plan
        pay *= CEREMONY_ONLY_PAY
    pay *= ROKUYO_PAY[g.rokuyo(day)] * bonus
    if g.month(day) == 6:
        pay *= JUNE_PAY
    pay = int(round(pay, -1))
    title = "%s家・%s家 %s%s" % (fam[0], fam[1], "挙式" if style == "CHAPEL" else "神前式",
                              "" if banquet else "（挙式のみ）")
    return Booking("WEDDING", day, title, people, pay, int(pay * 0.4), banquet=banquet,
                   rooms=rooms, style=style, family=fam)


def make_yuino(g):
    days = free_days(g, OFFER_LEAD, "wed")
    if not days:
        return None
    day = random.choice(days)
    fam = random.sample(FAMILIES, 2)
    people = random.randint(6, 8)
    pay = int(round(people * 30 + 150, -1))
    return Booking("YUINO", day, "%s家・%s家 結納" % (fam[0], fam[1]), people, pay,
                   int(pay * 0.3), family=fam)


def offer_popup(g, b, note=None):
    def accept(game):
        game.bookings.append(b)
        game.log("予約を受けました：%d日目 %s" % (b.day, b.title))

    lines = ["%d日後（%d日目・%d月・%s曜・%s）%s名" % (
        b.day - g.day, b.day, g.month(b.day), g.weekday_label(b.day), g.rokuyo(b.day),
        b.people)]
    if note:
        lines.append(note)
    if b.kind == "WEDDING" and g.month(b.day) == 6:
        lines.append("ジューンブライド！ 報酬+%d%%" % round((JUNE_PAY - 1) * 100))
    if b.guards:
        lines.append("要人が出席します。警備員の配置が必要です（報酬+%d%%）" %
                     round((VIP_CONF_PAY - 1) * 100))
    lines.append("当日までに必要なもの（○＝今の状態でOK）：")
    for text, ok in requirements(g, b):
        lines.append("　%s %s" % ("○" if ok else "×", text))
    if b.rooms:
        lines.append("※当日は一般客より団体客に部屋を優先します")
    if b.kind == "WEDDING" and b.style == "CHAPEL":
        lines.append("※チャペルへは外を歩きます。雨の日は渡り廊下があると安心")
    if b.kind == "WEDDING" and not b.banquet:
        lines.append("※宴会場が使えないため「挙式のみ」プラン（報酬控えめ）")
    if b.kind == "YUINO":
        lines.append("※成功すると、この両家の挙式の予約が入ります")
    lines.append("報酬 $%d　失敗時の違約金 $%d" % (b.pay, b.penalty))
    return {"title": "予約の打診：%s" % b.title, "lines": lines,
            "choices": [("引き受ける", True, accept), ("断る", True, None)]}


def wedding_chance(g):
    """daily chance of a wedding offer (shown in the chapel / shrine menu)"""
    if g.star < 2 or not g.has_venue():
        return 0.0
    p = WED_OFFER_P * WED_SEASON[g.season()]
    if g.bridal_boom > 0:
        p *= 1.6
    if june_near(g):
        p *= JUNE_OFFER
    return min(0.85, p)


def roll_offers(g):
    """STEP 13: weddings and meetings are offered on separate lines"""
    out = []
    if g.followups:
        fam = g.followups.pop(0)
        b = make_wedding(g, family=fam, bonus=1.2)
        if b:
            out.append(offer_popup(g, b, "結納を終えた両家から、挙式の依頼です！（報酬+20%）"))
    if g.star < 2:
        return out
    n_open = len(open_bookings(g))
    if n_open < MAX_BOOKINGS and random.random() < wedding_chance(g):
        b = make_wedding(g)
        if b:
            out.append(offer_popup(g, b))
            n_open += 1
    if (n_open < MAX_BOOKINGS and one(g, "YUINO") is not None
            and random.random() < YUINO_OFFER_P):
        b = make_yuino(g)
        if b:
            out.append(offer_popup(g, b))
            n_open += 1
    if n_open < MAX_BOOKINGS and random.random() < OFFER_CHANCE:
        b = make_conf_or_party(g)
        if b:
            out.append(offer_popup(g, b))
    return out


def roll_offer(g):
    offers = roll_offers(g)
    return offers[0] if offers else None


def cancel(g, b):
    fee = b.penalty // 2
    g.cash -= fee
    g.rep = clamp(g.rep - 1, 0, 100)
    b.status = "canceled"
    g.log("予約をキャンセル（-$%d・評判-1）" % fee)


# ------------------------------------------------------------
# the day itself
# ------------------------------------------------------------
def start_day(g):
    used = set()
    for b in today_bookings(g):
        if b.kind == "WEDDING":
            start_wedding(g, b)
        elif b.kind == "YUINO":
            start_yuino(g, b)
        if b.meet:
            rooms = [c for c in meeting_rooms(g) if c not in used][:b.meet]
            b.rooms_used = rooms
            used.update(rooms)
            for k, c in enumerate(rooms):
                n = b.people // len(rooms) + (1 if k < b.people % len(rooms) else 0)
                add_visitors(g, c, min(n, 10), MEET_ARRIVE, MEET_END, 13, b)
            g.add_timer(MEET_T, lambda b=b: check_meeting(g, b))
        if b.rooms:
            want = "TWIN" if b.kind == "WEDDING" else "SINGLE"
            arrive = WED_STAY_ARRIVE if b.kind == "WEDDING" else GROUP_ARRIVE
            gtype = "TOURIST" if b.kind == "WEDDING" else "BUSINESS"
            got = g.hold_rooms(b, b.rooms, want)             # STEP 16: keep the rooms
            if len(got) < b.rooms:
                g.log("%s：客室が%d室しか確保できない！" % (b.title, len(got)))
            for k in range(b.rooms):
                g.add_arrival(random.randint(*arrive), gtype, price_mult=0.0, nights=1,
                              group=b, want=want)
        if b.banquet and b.kind in ("CONF", "PARTY"):
            hall = banquet_hall(g)
            if hall is not None:
                n = b.people if b.kind == "PARTY" else b.people - b.rooms
                add_visitors(g, hall, min(n, 24), PARTY_ARRIVE, PARTY_END,
                             14 if b.kind == "PARTY" else 13, b)
            g.add_timer(BANQ["serve"], lambda b=b: serve_banquet(g, b))
        g.log("本日の予約：%s" % b.title)
    if g.weekday() in ("MON", "TUE", "WED", "THU", "FRI"):
        p = 0.25 + 0.5 * g.biz_share() * min(1.2, g.rep / 60)
        for c in meeting_rooms(g):
            if c in used or random.random() > p:
                continue
            c.rented = True
            add_visitors(g, c, random.randint(3, 7), MEET_ARRIVE, RENTAL_END, 5)
            g.add_timer(RENTAL_END, lambda c=c: rental_paid(g, c))


def start_wedding(g, b):
    v = venue_cell(g, b.style)
    dress = one(g, "DRESS")
    b.dress_ok = dress is not None
    if v is None:
        g.add_timer(CEREMONY_T, lambda: setattr(b, "ceremony_ok", False))
        return
    b.cells_used = [v] + ([dress] if dress else [])
    guests = min(b.people - 2, 26)
    add_visitors(g, v, guests, WED_ARRIVE, 99999, 13, b)
    first = dress if dress else v
    for who, col in (("BRIDE", 7), ("GROOM", 1)):
        def come(who=who, col=col):
            seat = seat_pt(first, 0) if (who == "BRIDE" and dress) else altar_pt(v, who)
            vis = Visitor(g.main, first if who == "BRIDE" else v, seat, 99999, col, b, who)
            g.visitors.append(vis)
        g.add_timer(WED_ARRIVE - 60, come)
    g.add_timer(CEREMONY_T - 140, lambda: to_altar(g, b, v))
    g.add_timer(CEREMONY_T, lambda: check_ceremony(g, b, v))
    g.add_timer(TO_RECEPTION_T, lambda: to_reception(g, b))
    if b.banquet:
        g.add_timer(RECEPTION_T, lambda: serve_banquet(g, b))
        suite, _ = g.celeb_suite()                       # STEP 16: bridal suite
        if suite is not None and g.tonight_free(suite) and not getattr(b, "couple_stay", False):
            g.hold(suite, "BRIDE", b)
            g.add_arrival(WED_END + 40, "TOURIST", price_mult=0.0, nights=1,
                          group=b, want="SUITE", couple=True)
            g.log("%s号室をブライダルスイートとして確保" % suite.number())
    if b.banquet and random.random() < 0.4:
        g.add_timer(RECEPTION_T + 100, lambda: gift_check(g, b))


def gift_check(g, b):
    sec = g.security(g.main)
    if random.random() < sec:
        b.gift = "safe"
        g.log("%s：警備員が引き出物を守った" % b.title)
    else:
        b.gift = "lost"
        g.log("%s：引き出物が紛失！" % b.title)


def booking_visitors(g, b):
    return [v for v in g.visitors if v.booking is b and v.state != "gone"]


def to_altar(g, b, v):
    for vis in booking_visitors(g, b):
        if vis.wrole == "BRIDE":
            vis.cell = v
            vis.goal = v.pos(*altar_pt(v, "BRIDE"))
            vis.state = "enter"


def check_ceremony(g, b, v):
    b.ceremony_ok = g.exists(v) and v.is_open()
    if b.ceremony_ok:
        g.log("%s：%sで挙式！" % (b.title, b.venue_label()))
        g.confetti = (v, 150)
    else:
        g.log("%s：式場が使えない！" % b.title)


def to_reception(g, b):
    hall = banquet_hall(g) if b.banquet else None
    vs = booking_visitors(g, b)
    for i, vis in enumerate(vs):
        if hall is None:
            vis.state = "leave"
            vis.goal = g.exit_goal(vis)
            continue
        vis.cell = hall
        if vis.wrole:
            seat = (hall.cx + (-6 if vis.wrole == "GROOM" else 6), hall.depth_y(66))
        else:
            seat = seat_pt(hall, i)
        vis.goal = hall.pos(*seat)
        vis.leave_t = WED_END + random.randint(0, 30)
        vis.state = "enter"
    if hall is not None:
        b.cells_used.append(hall)


def start_yuino(g, b):
    room = one(g, "YUINO")
    if room is None:
        b.ceremony_ok = False
        return
    b.cells_used = [room]
    add_visitors(g, room, min(b.people, 8), YUINO_ARRIVE, YUINO_END, 2, b)
    g.add_timer(YUINO_T, lambda: setattr(b, "ceremony_ok", g.exists(room)))


def rental_paid(g, c):
    if not c.rented:
        return
    g.cash += RENTAL_PRICE
    g.d_income += RENTAL_PRICE
    g.d_rental += RENTAL_PRICE
    c.rented = False
    g.log("会議室の貸し出し +$%d" % RENTAL_PRICE)


def check_meeting(g, b):
    ok = len([c for c in b.rooms_used if c.is_open() and g.exists(c)]) >= b.meet
    b.meet_ok = ok
    if not ok:
        g.log("%s：会議室が足りない！" % b.title)
    if b.guards:
        b.guard_ok = g.guard_count() >= b.guards
        if not b.guard_ok:
            g.log("%s：警備員が足りない！" % b.title)


def serve_banquet(g, b):
    hall = banquet_hall(g)
    if hall is None or not hall.is_open():
        b.served = 0
        g.log("%s：宴会場が使えない！" % b.title)
        return
    cooks = g.ready_cooks(hall)
    n = min(banquet_capacity(g, ready_only=True), b.people)
    b.served = n
    for st in cooks:
        st.fatigue = clamp(st.fatigue + 15, 0, 100)
        st.exp += 400
    if n < b.people:
        g.log("%s：料理が%d食足りない！" % (b.title, b.people - n))
    else:
        g.log("%s：%s%d食を提供" % (b.title, "披露宴の料理" if b.kind == "WEDDING"
                                    else "宴会料理", n))
    h = hall.hygiene
    hall.hygiene = max(0.0, hall.hygiene - BANQ["dirt"] * n)
    if n and h < HYGIENE_DANGER:
        p = POISON_MAX_P * (HYGIENE_DANGER - h) / HYGIENE_DANGER
        if random.random() < p:
            n_sick = max(1, n // 3)
            b.poison = True
            hall.closed_days = POISON_CLOSE_DAYS
            g.cash -= POISON_COMP * n_sick
            g.rep = clamp(g.rep - POISON_REP, 0, 100)
            g.d_poison += n_sick
            popup = poisoning_popup(g, hall, n_sick)
            g.events.note(g, popup)
            g.pending.append(popup)


def evaluate(g, b):
    parts = []
    lines = []
    bonus = 1.0
    if b.kind in ("WEDDING", "YUINO"):
        ok = bool(b.ceremony_ok)
        parts.append(1.0 if ok else 0.0)
        lines.append("%s　%s" % ("挙式" if b.kind == "WEDDING" else "結納",
                                "○" if ok else "× 会場がなかった"))
    if b.kind == "WEDDING":
        parts.append(1.0 if b.dress_ok else 0.4)
        lines.append("花嫁の支度　%s" % ("○" if b.dress_ok else "△ 衣装室がなかった"))
        if b.wet:
            parts.append(clamp(1.0 - b.wet / max(1, b.people) * 1.5, 0.0, 1.0))
            lines.append("天気　× 雨で%d人が濡れた（渡り廊下で防げる）" % b.wet)
        if b.gift == "lost":
            parts.append(0.4)
            lines.append("引き出物　× 紛失騒ぎ（警備員がいれば防げた）")
        elif b.gift == "safe":
            lines.append("引き出物　○ 警備員が不審者を見張った")
        if getattr(b, "couple_stay", False):
            lines.append("新郎新婦がブライダルスイートで一泊　評判+%d" % COUPLE_REP)
            g.rep = clamp(g.rep + COUPLE_REP, 0, 100)
        if b.style == "CHAPEL" and g.chapel_garden():
            bonus += GARDEN_WED_BONUS
            lines.append("隣の庭園で記念撮影！ 報酬+%d%%" % round(GARDEN_WED_BONUS * 100))
    if b.meet:
        ok = bool(b.meet_ok)
        parts.append(1.0 if ok else 0.0)
        lines.append("会議室　%s" % ("○" if ok else "× 足りなかった"))
    if b.guards:
        ok = bool(b.guard_ok)
        parts.append(1.0 if ok else 0.2)
        lines.append("要人の警備　%s" % ("○" if ok else "× 警備員が足りなかった"))
    if b.banquet:
        r = 0.0 if b.poison else (b.served or 0) / b.people
        parts.append(r)
        lines.append("%s　%d/%d食%s" % ("披露宴" if b.kind == "WEDDING" else "宴会料理",
                                       b.served or 0, b.people,
                                       "（食中毒）" if b.poison else ""))
    if b.rooms:
        parts.append(b.checked_in / b.rooms)
        lines.append("宿泊する招待客の部屋　%d/%d室" % (b.checked_in, b.rooms))
    score = sum(parts) / len(parts) if parts else 1.0
    big = b.kind == "WEDDING"
    if score >= 0.99:
        amount = int(b.pay * bonus)
        up = 5 if big else 3
        g.rep = clamp(g.rep + up, 0, 100)
        head, result = "大成功！ 報酬 +$%d　評判 +%d" % (amount, up), "成功"
        key = "WEDDING" if b.kind == "WEDDING" else ("MICE" if b.kind in ("CONF", "PARTY")
                                                    else b.kind)
        g.stats[key] = g.stats.get(key, 0) + 1
        if b.kind == "YUINO":
            g.followups.append(b.family)
            lines.append("両家から挙式の相談を受けました（明日、打診が届きます）")
    elif score >= 0.5:
        amount = int(b.pay * score * bonus)
        g.rep = clamp(g.rep - 1, 0, 100)
        head = "一部に不満… 報酬 +$%d（%d%%）評判 -1" % (amount, int(score * 100))
        result = "一部"
    else:
        amount = -b.penalty
        down = 8 if big else 5
        g.rep = clamp(g.rep - down, 0, 100)
        head, result = "失敗… 違約金 -$%d　評判 -%d" % (b.penalty, down), "失敗"
    g.cash += amount
    if amount > 0:
        g.d_income += amount
    g.d_booking.append((b.title, result, amount))
    b.status = "done"
    g.log("%s：%s" % (b.title, result))
    return {"title": "予約の結果：%s" % b.title, "lines": lines + [head],
            "choices": [("OK", True, None)]}
