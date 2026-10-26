# ============================================================
# security.py  -  guards, cameras, incidents
#
#   security(b) in [0, 0.9] for each building:
#       patrolling guards in b   : +0.35 each
#       camera coverage of b     : +0.45 x share of floors with cameras
#                                  (+0.15 only if nobody watches the monitors)
#   Each incident is PREVENTED with probability = security of the building.
# ============================================================
import random

from data import (INCIDENTS, INCIDENT_BASE, INCIDENT_PER_GUEST, THEFT_COMP, FIRE_COST,
                  FIRE_DAYS, clock_to_t, clamp)


def plan_incidents(g):
    """called every morning: schedule today's incidents"""
    guests = sum(1 for c in g.rooms() if c.state == "occupied") + len(g.arrivals)
    lam = (INCIDENT_BASE + INCIDENT_PER_GUEST * guests) * g.diff["incident"]
    if g.crime_wave > 0:
        lam *= 2.2
    if g.weekday() in ("FRI", "SAT"):
        lam *= 1.2
    n = 0
    while random.random() < lam / (n + 1) and n < 4:
        n += 1
    for _ in range(n):
        kinds = list(INCIDENTS)
        ws = [INCIDENTS[k]["weight"] * (1.8 if k == "DRUNK" and g.has_bar() else 1.0)
              for k in kinds]
        k = random.choices(kinds, weights=ws)[0]
        if k == "DRUNK":
            t = random.randint(clock_to_t(21), clock_to_t(23, 30))
        elif k == "PROWLER":
            t = random.randint(clock_to_t(8), clock_to_t(23))
        else:
            t = random.randint(clock_to_t(9), clock_to_t(23))
        g.add_timer(t, lambda k=k: incident(g, k))


def target_building(g, kind):
    bs = [b for b in g.buildings if not b.fixed()]
    if kind == "DRUNK" and g.has_bar():
        return g.main
    ws = [1 + sum(1 for c in g.rooms() if c.b is b and c.state == "occupied") for b in bs]
    return random.choices(bs, weights=ws)[0]


def incident(g, kind):
    b = target_building(g, kind)
    room = None
    if kind in ("THEFT", "FIRE"):
        cands = [c for c in g.rooms() if c.b is b and
                 (c.state == "occupied" if kind == "THEFT" else c.state != "broken")]
        if not cands:
            return
        room = random.choice(cands)
    label = INCIDENTS[kind]["label"]
    sec = g.security(b)
    where = "%s%s" % (b.name, ("%s号室" % room.number()) if room else "")
    if random.random() < sec:
        who = g.who_prevented(b)
        g.d_sec["prevented"] += 1
        g.rep = clamp(g.rep + 0.3, 0, 100)
        g.log("%sが%sの%sを未然に防いだ！" % (who, b.name, label))
        g.sec_flash = (b, 60)
        return
    g.d_sec["happened"] += 1
    lines = []
    if kind == "THEFT":
        room.guest.robbed = True
        g.cash -= THEFT_COMP
        g.rep = clamp(g.rep - 3, 0, 100)
        lines = ["%sで宿泊客の財布が盗まれました。" % where,
                 "お見舞い金 -$%d　評判 -3" % THEFT_COMP]
    elif kind == "DRUNK":
        g.rep = clamp(g.rep - 1.5, 0, 100)
        lines = ["%sで酔った客が大声で騒いでいます。" % b.name,
                 "周りの客から苦情が殺到… 評判 -1.5"]
    elif kind == "FIRE":
        found = random.random() < 0.3 + 0.7 * g.camera_share(b)
        if found:
            g.cash -= FIRE_COST // 4
            lines = ["%sでボヤ！ カメラが煙を見つけ、すぐ消し止めました。" % where,
                     "修理費 -$%d" % (FIRE_COST // 4)]
        else:
            if room.guest is not None:
                room.guest.robbed = True
            room.state = "broken"
            room.broken_days = FIRE_DAYS
            g.cash -= FIRE_COST
            g.rep = clamp(g.rep - 5, 0, 100)
            lines = ["%sで火事！ 発見が遅れました。" % where,
                     "部屋は%d日間使えません。修理費 -$%d　評判 -5" % (FIRE_DAYS, FIRE_COST)]
            g.fire_fx = (room, 120)
    elif kind == "PROWLER":
        g.rep = clamp(g.rep - 1.5, 0, 100)
        lines = ["%sに不審者が入り込み、客が怖がっています。" % b.name, "評判 -1.5"]
    lines.append("ヒント：警備員の巡回と、警備室で見張る防犯カメラ")
    lines.append("%sの防犯レベル：%d%%" % (b.name, sec * 100))
    popup = {"title": "!! %s発生 !!" % label, "lines": lines,
             "choices": [("OK…", True, None)]}
    g.events.note(g, popup)
    g.pending.append(popup)
