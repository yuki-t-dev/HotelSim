# ============================================================
# shops.py  -  STEP 19: kiosk shops, brand tenants, outside shoppers
#
#   SHOP   (売店)       : no staff. Sells to people who WALK PAST its door
#                         (guests and visitors in the corridor of that floor).
#                         Busy places sell more: the lobby, a shopping building.
#                         Rainy days: umbrellas sell well.
#   TENANT (テナント区画): no staff. A brand moves in when its conditions are met
#                         (offer in the morning). Pays fixed rent every night,
#                         plus a bonus for every VIP / celebrity guest that day.
#                         If the reputation stays below the brand's line, it
#                         warns you and finally moves out.
#   MALL   (商業棟)      : building for restaurants / shops / tenants (no rooms).
#                         Shoppers from the street come in through its entrance.
# ============================================================
import random

from data import (BRANDS, BRAND_ORDER, SHOP_P, SHOP_PRICE, UMBRELLA_PRICE, TENANT_WARN,
                  TENANT_LEAVE, TENANT_OFFER_P, SHOPPER_BASE, SHOPPER_COLOR, SW, clock_to_t,
                  in_corridor)
from model import Visitor


def key_of(c):
    return (c.b.kind, c.b.no, c.f, c.s)


def shop_cells(g):
    return list(g.cells(("SHOP",)))


def tenant_cells(g):
    return list(g.cells(("TENANT",)))


def brand_of(c):
    k = getattr(c, "tenant", None)
    return BRANDS[k] if k else None


# ------------------------------------------------------------
# passing trade (called every tick)
# ------------------------------------------------------------
def passing_trade(g):
    shops = [c for c in shop_cells(g) if c.is_open()]
    if not shops:
        return
    rain = g.weather_at() in ("RAIN", "SNOW")
    people = [a for a in g.guests if a.state not in ("gone", "checkin", "in_room")]
    people += [v for v in g.visitors if v.state != "gone"]
    for c in shops:
        half = SW * c.w // 2
        k = key_of(c)
        for a in people:
            if a.transit > 0 or a.b is not c.b or a.floor != c.f or not in_corridor(a.y):
                continue
            if abs(a.x - c.cx) > half:
                continue
            seen = getattr(a, "shopped", None)
            if seen is None:
                seen = a.shopped = set()
            if k in seen:
                continue
            seen.add(k)
            p = SHOP_P.get(getattr(a, "gtype", "VISIT"), SHOP_P["VISIT"])
            umbrella = rain and random.random() < 0.15
            if not umbrella and random.random() >= p:
                continue
            price = UMBRELLA_PRICE if umbrella else random.randint(*SHOP_PRICE)
            g.cash += price
            g.d_income += price
            g.d_shop += price
            c.served_today += 1
            c.sales_today = getattr(c, "sales_today", 0) + price
            if umbrella:
                g.d_umbrella += 1
    # outside shoppers who came FOR this shop buy when they reach it
    for v in g.visitors:
        c = v.cell
        if v.color != SHOPPER_COLOR or v.state != "stay" or c is None or c.kind != "SHOP":
            continue
        seen = getattr(v, "shopped", None)
        if seen is None:
            seen = v.shopped = set()
        k = ("in",) + key_of(c)
        if k in seen:
            continue
        seen.add(k)
        if random.random() < 0.8:
            price = random.randint(*SHOP_PRICE) + 3
            g.cash += price
            g.d_income += price
            g.d_shop += price
            c.served_today += 1
            c.sales_today = getattr(c, "sales_today", 0) + price


# ------------------------------------------------------------
# tenants
# ------------------------------------------------------------
def brand_ok(g, key):
    """[(text, ok)] conditions of a brand"""
    b = BRANDS[key]
    n_su = sum(1 for c in g.rooms() if c.kind == "SUITE")
    out = [("★%d以上" % b["star"], g.star >= b["star"]),
           ("評判%d以上" % b["rep"], g.rep >= b["rep"])]
    if b.get("suites"):
        out.append(("スイート%d室以上" % b["suites"], n_su >= b["suites"]))
    return out


def brand_ready(g, key):
    return all(ok for _, ok in brand_ok(g, key))


def taken(g):
    return {c.tenant for c in tenant_cells(g) if getattr(c, "tenant", None)}


def best_brand(g):
    used = taken(g)
    ready = [k for k in BRAND_ORDER if k not in used and brand_ready(g, k)]
    return ready[-1] if ready else None      # BRAND_ORDER is cheap -> luxury


def tenant_offer(g):
    """morning: a brand asks to move into a vacant space"""
    vacant = [c for c in tenant_cells(g) if not getattr(c, "tenant", None)]
    if not vacant or random.random() > TENANT_OFFER_P:
        return None
    key = best_brand(g)
    if key is None:
        return None
    c = vacant[0]
    b = BRANDS[key]

    def accept(game):
        c.tenant = key
        c.tenant_warn = 0
        game.log("%sが%sに入居しました" % (b["label"], c.b.name))

    return {"title": "テナントの入居希望：%s" % b["label"],
            "lines": ["%s（%s）が入居を希望しています。" % (b["label"], b["kind"]),
                      "家賃 $%d/日　VIP・有名人1組につき +$%d" % (b["rent"], b["bonus"]),
                      "条件：評判%d以上を保つこと" % b["rep"],
                      "（下回り続けると退去されます）"],
            "choices": [("契約する", True, accept), ("見送る", True, None)]}


def end_tenant(g, c):
    b = brand_of(c)
    if b:
        g.log("%sとの契約を終了しました" % b["label"])
    c.tenant = None
    c.tenant_warn = 0


def tenants_night(g, vips):
    """rent + VIP bonus, reputation check. Returns (rent, bonus, popups)"""
    rent = bonus = 0
    pops = []
    for c in tenant_cells(g):
        b = brand_of(c)
        if not b:
            continue
        rent += b["rent"]
        bonus += b["bonus"] * vips
        if g.rep < b["rep"]:
            c.tenant_warn = getattr(c, "tenant_warn", 0) + 1
            if c.tenant_warn >= TENANT_LEAVE:
                pops.append({"title": "!! テナント退去 !!",
                             "lines": ["%sが退去しました。" % b["label"],
                                       "評判が%d未満の日が続いたためです。" % b["rep"]],
                             "choices": [("OK…", True, None)]})
                c.tenant = None
                c.tenant_warn = 0
            elif c.tenant_warn == TENANT_WARN:
                pops.append({"title": "テナントからの苦情：%s" % b["label"],
                             "lines": ["「ホテルの評判が落ちています。」",
                                       "評判%d以上に戻さないと、あと%d日で退去します。" % (
                                           b["rep"], TENANT_LEAVE - c.tenant_warn)],
                             "choices": [("OK", True, None)]})
        else:
            c.tenant_warn = 0
    return rent, bonus, pops


# ------------------------------------------------------------
# outside shoppers (shopping building + brand stores)
# ------------------------------------------------------------
def shopper_targets(g):
    out = []
    for c in tenant_cells(g):
        b = brand_of(c)
        if b:
            out += [c] * b["pull"]
    for c in shop_cells(g):
        if c.b.kind == "MALL":
            out += [c, c]
    return out


def plan_shoppers(g):
    targets = shopper_targets(g)
    if not targets:
        return
    n = SHOPPER_BASE + len(targets)
    if any(g.trait(b.lot) == "STATION" for b in g.buildings if b.kind == "MALL"):
        n = int(n * 1.5)
    n = int(n * (0.6 + g.rep / 100) * {"RAIN": 0.7, "SNOW": 0.6}.get(g.weather_at(), 1.0))
    for i in range(min(n, 24)):
        c = random.choice(targets)
        t = random.randint(clock_to_t(10), clock_to_t(16))
        g.add_timer(t, lambda c=c, i=i, t=t: add_shopper(g, c, i, t))


def add_shopper(g, c, i, t):
    if not g.exists(c):
        return
    entry = c.b if c.b.kind == "MALL" else g.main
    span = 12 * c.w
    seat = (c.cx - span + (i % 5) * (span // 2), c.depth_y(30 + (i % 3) * 12))
    v = Visitor(entry, c, seat, t + random.randint(120, 260), SHOPPER_COLOR)
    g.visitors.append(v)
    if c.kind == "TENANT" and getattr(c, "tenant", None):
        g.d_tenant_visitors += 1
