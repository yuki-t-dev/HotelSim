# ============================================================
# resort.py  -  onsen / spa, guest reviews, rival hotel, routes to the 4th star
# ============================================================
import math
import random

from data import (ONSEN_SAT, OPEN_AIR_SAT, SPA_SAT, REVIEW_KEEP, REVIEW_N, REVIEW_DEMAND,
                  RIVAL_NAME, RIVAL_REP0, PRICE_WAR_CUT, PRICE_WAR_OK, HYGIENE_DANGER,
                  LOT_TRAITS, GUEST_TYPES, ROUTE_ORDER, SAUNA_CAP, SAUNA_SAT, clamp)


def one(g, kind):
    cs = list(g.cells((kind,)))
    return cs[0] if cs else None


def open_air(c):
    if getattr(c, "lv", 1) >= 2:                 # STEP 17: built as an open-air bath
        return True
    return (not c.b.is_main()) and LOT_TRAITS.get(c.b.lot) in ("OCEAN", "FOREST")


def sauna(c):
    return getattr(c, "lv", 1) >= 3


def bath_time(g):
    onsen, spa = one(g, "ONSEN"), one(g, "SPA")
    guests = [x for x in g.guests if x.state == "in_room" and not x.sick]
    random.shuffle(guests)
    n_on = n_spa = 0
    if onsen is not None and onsen.is_open():
        winter = 1.4 if g.season() == "WINTER" else 1.0
        cap = onsen.spec["cap"] + (SAUNA_CAP if sauna(onsen) else 0)
        for x in guests:
            p = (0.55 if x.gtype == "TOURIST" else 0.35) * winter
            if n_on < cap and random.random() < p:
                n_on += 1
                x.bath = onsen
        onsen.served_today += n_on
        onsen.hygiene = max(0.0, onsen.hygiene - onsen.spec["dirt"] * n_on)
    if spa is not None and spa.is_open():
        cap = spa.spec["cap"]
        for x in guests:
            p = 0.8 if x.vip else (0.3 if x.gtype == "TOURIST" else 0.12)
            if n_spa < cap and random.random() < p:
                n_spa += 1
                x.spa = True
        rev = n_spa * spa.spec["price"]
        g.cash += rev
        g.d_income += rev
        g.d_resort += rev
        spa.served_today += n_spa
        spa.hygiene = max(0.0, spa.hygiene - spa.spec["dirt"] * n_spa)
    if n_on or n_spa:
        g.log("湯上がり：大浴場%d人・スパ%d人%s" % (n_on, n_spa,
                                            "（+$%d）" % g.d_resort if n_spa else ""))


def resort_score(g, x, note):
    c = getattr(x, "bath", None)
    if c is not None:
        if c.hygiene < HYGIENE_DANGER:
            note(-1.0, "お風呂が汚れていた")
        else:
            note(ONSEN_SAT[x.gtype], "大浴場で疲れが取れた")
            if open_air(c):
                note(OPEN_AIR_SAT, "露天風呂からの眺めが最高")
            if g.season() == "WINTER":
                note(0.3, "冬の温泉はたまらない")
            if sauna(c):
                note(SAUNA_SAT * (2 if g.season() == "WINTER" else 1), "サウナで整った")
    if getattr(x, "spa", False):
        note(SPA_SAT, "スパで癒された")


# ---------------- reviews ----------------
def stars_of(score):
    if score < -1.5:
        return 1
    if score < 0.0:
        return 2
    if score < 1.5:
        return 3
    if score < 3.0:
        return 4
    return 5


def add_review(g, x, score, notes):
    st = stars_of(score)
    good = sorted([n for n in notes if n[0] > 0], key=lambda n: -n[0])
    bad = sorted([n for n in notes if n[0] < 0], key=lambda n: n[0])
    if st <= 2 and bad:
        text = bad[0][1]
    elif st >= 4 and good:
        text = good[0][1]
    elif bad and (not good or -bad[0][0] > good[0][0]):
        text = bad[0][1]
    elif good:
        text = good[0][1]
    else:
        text = "普通のホテルでした"
    who = "有名人" if x.celeb else GUEST_TYPES[x.gtype]["label"]
    g.reviews.append((g.day, st, who, text))
    g.reviews = g.reviews[-REVIEW_KEEP:]
    g.d_reviews.append(st)
    g.popups.append((x.b, x.floor, x.x, x.y, st, 45))


def review_avg(g):
    rs = [r[1] for r in g.reviews[-REVIEW_N:]]
    return sum(rs) / len(rs) if rs else 3.0


def review_mult(g):
    if not g.reviews:
        return 1.0
    return 1.0 + REVIEW_DEMAND * (review_avg(g) - 3.0)


# ---------------- rival ----------------
def open_rival(g):
    g.rival = dict(name=RIVAL_NAME, rep=float(RIVAL_REP0), war=0)


def rival_mult(g):
    r = g.rival
    if r is None:
        return 1.0
    share = 1.0 / (1.0 + math.exp((r["rep"] - g.rep) / 12.0))
    m = 0.7 + 0.6 * share
    if r["war"] > 0 and g.prices["SINGLE"] > g.fair("SINGLE") * PRICE_WAR_OK:
        m *= PRICE_WAR_CUT
    return m


def rival_day(g):
    r = g.rival
    if r is None:
        return
    target = 55 + 8 * g.star
    r["rep"] = clamp(r["rep"] + (target - r["rep"]) * 0.05 + random.uniform(-1.2, 1.2),
                     30, 95)
    if r["war"] > 0:
        r["war"] -= 1


# ---------------- routes to the 4th star ----------------
def route_conditions(g, key):
    rooms = g.rooms()
    if key == "LODGING":
        n_su = sum(1 for c in rooms if c.kind == "SUITE")
        return [("客室", len(rooms), 20, "%d/20室" % len(rooms)),
                ("スイート", n_su, 3, "%d/3室" % n_su),
                ("評判", g.rep, 85, "%.1f/85" % g.rep)]
    if key == "WEDDING":
        n = g.stats.get("WEDDING", 0)
        return [("挙式の大成功", n, 8, "%d/8回" % n),
                ("評判", g.rep, 80, "%.1f/80" % g.rep)]
    if key == "MICE":
        n = g.stats.get("MICE", 0)
        return [("会議・宴会の大成功", n, 10, "%d/10回" % n),
                ("評判", g.rep, 80, "%.1f/80" % g.rep)]
    on = 1 if one(g, "ONSEN") else 0
    sp = 1 if one(g, "SPA") else 0
    oc = sum(1 for c in rooms if g.is_ocean(c))
    avg = review_avg(g) if g.reviews else 0.0
    return [("大浴場とスパ", on + sp, 2, "%d/2" % (on + sp)),
            ("海側の客室", oc, 8, "%d/8室" % oc),
            ("口コミ平均", avg, 4.0, "%.1f/4.0" % avg),
            ("評判", g.rep, 80, "%.1f/80" % g.rep)]


def route_done(g, key):
    return all(cur >= need for _, cur, need, _ in route_conditions(g, key))


def route_progress(g, key):
    conds = route_conditions(g, key)
    return sum(min(1.0, cur / need) if need else 1.0 for _, cur, need, _ in conds) / len(conds)


def best_route(g):
    return max(ROUTE_ORDER, key=lambda k: route_progress(g, k))
