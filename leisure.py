# ============================================================
# leisure.py  -  STEP 20: pool and gym
#
#   POOL (2 slots)  open 10:00-18:00, swimmers counted at 16:00
#       season : summer x2.5, spring / autumn x1, winter CLOSED (unless Lv2 indoor)
#       guests swim for free (satisfaction), outside guests buy a day pass
#       LIFEGUARD : a guard posted at the pool. Without one, accidents can happen
#                   (rep -6, pool closed 2 days)
#       Lv2 indoor pool : open all year
#       Lv3 night pool  : extra session at 20:00 (adults, $18, very popular in summer)
#   GYM (1 slot)    no staff needed
#       business guests love it (satisfaction)
#       local MEMBERS pay every night: steady income that ignores season / weather
#       members grow with reputation (+ station lots), capped by capacity (Lv)
# ============================================================
import random

from data import (POOL_T, NIGHT_POOL_T, POOL_SEASON, POOL_CAP, DAYPASS, NIGHT_PASS,
                  POOL_OUT_BASE, POOL_ACCIDENT_P, POOL_ACCIDENT_REP, POOL_CLOSE_DAYS,
                  POOL_SAT, GYM_SAT, GYM_FEE, GYM_CAP, GYM_GROW, LEISURE_COLOR, clamp)
from model import Visitor


def one(g, kind):
    cs = list(g.cells((kind,)))
    return cs[0] if cs else None


def indoor(c):
    return getattr(c, "lv", 1) >= 2


def night_pool(c):
    return getattr(c, "lv", 1) >= 3


def pool_season_mult(g, c):
    m = POOL_SEASON[g.season()]
    if m == 0 and indoor(c):
        m = 0.6                              # indoor pool in winter
    if not indoor(c):
        m *= {"RAIN": 0.3, "SNOW": 0.0, "CLOUD": 0.8}.get(g.weather_at(), 1.0)
    return m


def pool_open(g, c):
    return c.is_open() and pool_season_mult(g, c) > 0


def lifeguards(g, c):
    return g.guards_on(("FAC", c))


# ------------------------------------------------------------
# pool sessions
# ------------------------------------------------------------
def pool_time(g, night=False):
    c = one(g, "POOL")
    if c is None or not pool_open(g, c):
        return
    if night and not night_pool(c):
        return
    m = pool_season_mult(g, c)
    cap = POOL_CAP + (6 if indoor(c) else 0)
    guests = [x for x in g.guests if x.state == "in_room" and not x.sick]
    random.shuffle(guests)
    n_in = 0
    for x in guests:
        p = (0.35 if x.gtype == "TOURIST" else 0.12) * m * (0.6 if night else 1.0)
        if n_in < cap and random.random() < p:
            n_in += 1
            x.swam = True
    out = c.out_plan.get("night" if night else "day", 0)
    out = max(0, min(out, cap - n_in))
    price = NIGHT_PASS if night else DAYPASS
    rev = out * price
    g.cash += rev
    g.d_income += rev
    g.d_leisure += rev
    g.d_pool_out += out
    n = n_in + out
    c.served_today += n
    c.hygiene = max(0.0, c.hygiene - 0.5 * n)
    if n:
        g.log("%s：宿泊客%d人・外来%d人（+$%d）" % ("ナイトプール" if night else "プール",
                                            n_in, out, rev))
    # accident check (no lifeguard)
    if n and not lifeguards(g, c):
        if random.random() < POOL_ACCIDENT_P * min(2.0, n / 10.0):
            g.rep = clamp(g.rep - POOL_ACCIDENT_REP, 0, 100)
            c.closed_days = POOL_CLOSE_DAYS
            g.cash -= 300
            popup = {"title": "!! プールで事故 !!",
                     "lines": ["監視員がいないプールで、客がおぼれかけました。",
                               "命に別状はありませんが、大きく報道されています。",
                               "見舞金 -$300　評判 -%d　%d日間閉鎖" % (POOL_ACCIDENT_REP,
                                                             POOL_CLOSE_DAYS),
                               "ヒント：警備員をプールの監視員に配置しましょう"],
                     "choices": [("OK…", True, None)]}
            g.events.note(g, popup)
            g.pending.append(popup)


def plan_pool(g):
    """morning: how many outside swimmers come today (and show some of them)"""
    c = one(g, "POOL")
    if c is None:
        return
    plan = {"day": 0, "night": 0}
    if pool_open(g, c):
        m = pool_season_mult(g, c) * (0.6 + g.rep / 100)
        if g.weekday() in ("SAT", "SUN"):
            m *= 1.5
        plan["day"] = max(0, int(round(random.gauss(POOL_OUT_BASE * m, 1.5))))
        if night_pool(c):
            mn = min(m, 1.6)
            plan["night"] = max(0, int(round(random.gauss(POOL_OUT_BASE * 0.35 * mn, 1.0))))
    c.out_plan = plan
    for i in range(min(plan["day"], 8)):
        t = POOL_T - 300 + random.randint(0, 80)
        g.add_timer(t, lambda i=i, t=t: add_swimmer(g, c, i, t, 520))
    for i in range(min(plan["night"], 6)):
        t = NIGHT_POOL_T - 260 + random.randint(0, 60)
        g.add_timer(t, lambda i=i, t=t: add_swimmer(g, c, i + 3, t, 420))


def add_swimmer(g, c, i, t, stay):
    if not g.exists(c) or not c.is_open():
        return
    span = 20 * c.w
    seat = (c.cx - span + (i % 6) * (span // 3), c.depth_y(30 + (i // 6) * 18))
    v = Visitor(g.main, c, seat, t + stay + random.randint(0, 40), LEISURE_COLOR)
    g.visitors.append(v)


# ------------------------------------------------------------
# gym
# ------------------------------------------------------------
def gym_cap(c):
    return GYM_CAP[getattr(c, "lv", 1)]


def gym_day(g):
    """night: members pay, membership grows / shrinks. Returns fee"""
    c = one(g, "GYM")
    if c is None:
        g.gym_members = 0
        return 0
    target = gym_cap(c) * clamp((g.rep - 30) / 60.0, 0.1, 1.0)
    if any(g.trait(l) == "STATION" for l in g.lots):
        target *= 1.2
    target = min(gym_cap(c), target)
    if g.gym_members < target:
        g.gym_members = min(target, g.gym_members + GYM_GROW)
    else:
        g.gym_members = max(target, g.gym_members - GYM_GROW)
    if c.hygiene < 45:
        g.gym_members = max(0, g.gym_members - 2)          # dirty gym: members quit
    c.hygiene = max(0.0, c.hygiene - 0.15 * g.gym_members)
    fee = int(int(g.gym_members) * GYM_FEE)
    g.cash += fee
    g.d_income += fee
    return fee


# ------------------------------------------------------------
# satisfaction (called from checkout_score)
# ------------------------------------------------------------
def leisure_score(g, x, note):
    if getattr(x, "swam", False):
        note(POOL_SAT.get(x.gtype, 0.5), "プールで思いきり遊べた")
    gym = one(g, "GYM")
    if gym is not None and x.gtype == "BUSINESS":
        note(GYM_SAT, "朝のジムで体を動かせた")
