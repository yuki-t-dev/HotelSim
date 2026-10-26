# ============================================================
# events.py  -  random events (morning)
#
#   Each event = one function `fire(game)` + an entry in EVENTS.
#   fire() returns a POPUP:
#       {"title": str, "lines": [str, ...],
#        "choices": [(label, enabled, fn(game) or None), ...]}
# ============================================================
import random

from data import (ROLES, EVENT_CHANCE, EVENT_COOLDOWN, HYGIENE_WARN, clock_to_t,
                  POISON_CLOSE_DAYS, POISON_REP, POISON_COMP)


def ok_popup(title, lines):
    return {"title": title, "lines": lines, "choices": [("OK", True, None)]}


def ev_group_tour(g):
    n = random.randint(3, 5)
    t0 = random.randint(1000, 1300)

    def accept(game):
        for k in range(n):
            game.add_arrival(t0 + k * 12, "TOURIST", price_mult=0.8, nights=1, want="TWIN")
        game.log("%d組のツアー客を受け入れました" % n)

    return {
        "title": "イベント：ツアー団体",
        "lines": ["%d組（ツイン希望）のツアー団体が今夜の宿を探しています。" % n,
                  "宿泊料を2割引にしてほしいそうです。",
                  "現在の空室：%d室" % g.free_room_count()],
        "choices": [("受け入れる（%d組・8割の料金）" % n, True, accept),
                    ("断る", True, None)],
    }


def ev_festival(g):
    n = max(2, int(len(g.rooms()) * 0.4) + 1)
    for _ in range(n):
        g.add_arrival(random.randint(900, 1500), "TOURIST")
    return ok_popup("イベント：地元のお祭り",
                    ["今日は町でお祭りが開かれます！",
                     "観光客が%d組ほど多く来そうです。" % n])


def leak_candidates(g):
    return [c for c in g.rooms() if c.state in ("clean", "dirty") and c.claimed is None]


def ev_water_leak(g):
    room = random.choice(leak_candidates(g))
    prev = room.state
    room.state = "broken"
    room.broken_days = 99
    cost = 150

    def repair(game):
        game.cash -= cost
        room.state = "dirty" if prev == "dirty" else "clean"
        room.broken_days = 0
        game.log("%s号室を修理しました（-$%d）" % (room.number(), cost))

    def wait(game):
        room.broken_days = 2
        game.log("%s号室を2日間閉鎖します" % room.number())

    return {
        "title": "イベント：水漏れ発生！",
        "lines": ["%s号室で配管が破裂しました。" % room.number(),
                  "修理するまでこの部屋は使えません。"],
        "choices": [("すぐ修理する（$%d）" % cost, g.cash >= cost, repair),
                    ("待つ（2日間閉鎖・無料）", True, wait)],
    }


def ev_magazine(g):
    g.rep = min(100, g.rep + 3)
    return ok_popup("イベント：旅行雑誌の取材",
                    ["旅行雑誌でホテルが紹介されました！", "評判 +3"])


def ev_staff_cold(g):
    st = random.choice([s for s in g.staff if s.post is not None])
    st.fatigue = min(100, st.fatigue + 40)
    return ok_popup("イベント：スタッフが風邪",
                    ["%s（%s）が風邪をひきました。" % (st.name, ROLES[st.role]["label"]),
                     "疲労 +40。休ませると良さそうです。"])


def ev_inspection(g):
    shops = [c for c in g.hygiene_cells() if c.is_open()]
    lines = ["保健所の抜き打ち検査がありました。"]
    rep = 0
    fine = 0
    for c in shops:
        h = int(c.hygiene)
        if h >= 80:
            lines.append("%s：衛生度 %d　優良" % (c.label, h))
            rep += 1.5
        elif h >= HYGIENE_WARN:
            lines.append("%s：衛生度 %d　合格" % (c.label, h))
        else:
            lines.append("%s：衛生度 %d　罰金 $200" % (c.label, h))
            fine += 200
            rep -= 2
    g.cash -= fine
    g.rep = max(0, min(100, g.rep + rep))
    lines.append("評判 %+.1f　罰金 -$%d" % (rep, fine))
    return ok_popup("イベント：保健所の検査", lines)


def ev_cheap_supplier(g):
    def accept(game):
        game.cheap_food_days = 5
        game.log("格安業者と5日間の契約")

    return {
        "title": "イベント：格安業者の提案",
        "lines": ["業者がとても安い食材を提案してきました。",
                  "5日間：店の維持費0、料理の利益+30%",
                  "ただし衛生度が2倍の速さで下がります…"],
        "choices": [("契約する", True, accept), ("断る", True, None)],
    }


def ev_gourmet_blog(g):
    best = max(g.food_cells(), key=lambda c: c.hygiene)
    g.rep = min(100, g.rep + 4)
    g.food_boom = (best.kind, 2)
    return ok_popup("イベント：グルメブロガー",
                    ["有名ブロガーが%sを絶賛しました！" % best.label,
                     "評判 +4", "2日間、%sに客が多く入ります。" % best.label])


def ev_bridal_fair(g):
    g.bridal_boom = 5
    return ok_popup("イベント：ブライダル雑誌に掲載",
                    ["結婚情報誌で式場が紹介されました！",
                     "5日間、挙式の打診が届きやすくなります。"])


def ev_celebrity(g):
    """STEP 16: the suite is kept for the celebrity as soon as you accept"""
    suite, mover = g.celeb_suite()

    def accept(game):
        if mover is not None:
            game.move_guest(mover, game.move_target(mover, suite))
        game.hold(suite, "CELEB")
        game.add_arrival(clock_to_t(17), "TOURIST", price_mult=3.0, nights=1,
                         want="SUITE", celeb=True)
        game.add_timer(clock_to_t(23), game.celeb_check)
        game.log("有名人のために%s号室を確保しました" % suite.number())

    lines = ["人気俳優が今夜、お忍びで泊まりたいそうです。",
             "スイートの料金の3倍を払ってくれます。",
             "ただし記者に見つかると大騒ぎに…"]
    choices = []
    if suite is None:
        lines.append("!! 今夜使えるスイートがありません")
        choices.append(("スイートが空いていない", False, None))
    else:
        lines.append("%s号室（%s・防犯レベル%d%%）を確保します" % (
            suite.number(), suite.b.name, g.security(suite.b) * 100))
        if mover is None:
            choices.append(("引き受ける", True, accept))
        else:
            lines.append("今の宿泊客に別の部屋へ移ってもらう必要があります")
            choices.append(("お詫びして部屋を移ってもらう（$100・評判-1）", True, accept))
    choices.append(("断る", True, None))
    return {"title": "イベント：有名人の宿泊依頼", "lines": lines, "choices": choices}


def ev_safe_award(g):
    g.rep = min(100, g.rep + 3)
    return ok_popup("イベント：防犯優良ホテルに認定",
                    ["警察から「防犯優良ホテル」に認定されました！", "評判 +3"])


def ev_crime_wave(g):
    g.crime_wave = 3
    return ok_popup("イベント：近所で空き巣が多発",
                    ["近所でホテル荒らしが続いているそうです。",
                     "3日間、トラブルが起きやすくなります。",
                     "警備員や防犯カメラで備えましょう。"])


def ev_price_war(g):
    g.rival["war"] = 3
    return ok_popup("イベント：ライバルの値下げ攻勢",
                    ["%sが3日間の大幅値下げを始めました。" % g.rival["name"],
                     "シングルを適正価格の9割（$%d）以下にしないと" % int(g.fair("SINGLE") * 0.9),
                     "客が15%減ります。"])


def ev_rival_scandal(g):
    g.rival["rep"] = max(30, g.rival["rep"] - 10)
    return ok_popup("イベント：ライバルの不祥事",
                    ["%sで衛生問題が発覚したそうです。" % g.rival["name"],
                     "相手の評判 -10。こちらに客が流れてきそうです。"])


def ev_poaching(g):
    cands = [s for s in g.staff if s.post is not None and s.skill >= 2]
    st = random.choice(cands)
    raise_ = 10 * st.skill

    def keep(game):
        st.bonus += raise_
        game.log("%sの日給を$%d上げました" % (st.name, raise_))

    def let_go(game):
        if st in game.staff:
            game.unassign(st)
            game.staff.remove(st)
        game.log("%sがライバルホテルに移りました" % st.name)

    return {
        "title": "イベント：引き抜きの誘い",
        "lines": ["%s（%s %s）が" % (st.name, ROLES[st.role]["label"], st.stars()),
                  "%sから誘われています。" % g.rival["name"],
                  "日給を$%d上げれば残ってくれるそうです。" % raise_],
        "choices": [("昇給して引き止める（+$%d/日）" % raise_, True, keep),
                    ("送り出す", True, let_go)],
    }


def review_avg20(g):
    rs = g.reviews[-20:]
    return sum(r[1] for r in rs) / max(1, len(rs))


def ev_review_site(g):
    avg = review_avg20(g)
    if avg >= 4.0:
        g.rep = min(100, g.rep + 4)
        return ok_popup("イベント：口コミサイトで上位に",
                        ["口コミ平均%.1fで、ランキング上位に入りました！" % avg, "評判 +4"])
    g.rep = max(0, g.rep - 3)
    return ok_popup("イベント：口コミサイトで炎上",
                    ["口コミ平均%.1f…悪い口コミが拡散されました。" % avg,
                     "評判 -3　口コミで原因を確認しましょう"])


def poisoning_popup(g, cell, n_sick):
    comp = POISON_COMP * max(1, n_sick)
    return {
        "title": "!! 食中毒発生 !!",
        "lines": ["%sの%sで%d名が体調を崩しました。" % (cell.label, cell.spec["meal"], n_sick),
                  "衛生度はわずか%dでした。" % int(cell.hygiene),
                  "%sは%d日間の営業停止です。" % (cell.label, POISON_CLOSE_DAYS),
                  "賠償金 -$%d　評判 -%d" % (comp, POISON_REP),
                  "ヒント：店に清掃係を置きましょう。"],
        "choices": [("OK…", True, None)],
    }


EVENTS = [
    dict(id="GROUP_TOUR", cond=lambda g: len(g.rooms()) >= 4,
         weight=lambda g: 1.5 if g.weekday() in ("FRI", "SAT") else 1.0, fire=ev_group_tour),
    dict(id="FESTIVAL",
         cond=lambda g: g.season() in ("SUMMER", "AUTUMN") and len(g.rooms()) >= 3,
         weight=lambda g: 0.8, fire=ev_festival),
    dict(id="WATER_LEAK", cond=lambda g: len(g.rooms()) >= 3 and leak_candidates(g),
         weight=lambda g: 0.7, fire=ev_water_leak),
    dict(id="MAGAZINE", cond=lambda g: g.rep >= 58, weight=lambda g: 0.5, fire=ev_magazine),
    dict(id="STAFF_COLD", cond=lambda g: sum(1 for s in g.staff if s.post is not None) >= 3,
         weight=lambda g: 0.5 + (0.5 if g.season() == "WINTER" else 0.0),
         fire=ev_staff_cold),
    dict(id="INSPECTION", cond=lambda g: any(c.is_open() for c in g.hygiene_cells()),
         weight=lambda g: 0.9, fire=ev_inspection),
    dict(id="CHEAP_SUPPLIER", cond=lambda g: g.food_cells() and g.cheap_food_days <= 0,
         weight=lambda g: 0.6, fire=ev_cheap_supplier),
    dict(id="GOURMET_BLOG",
         cond=lambda g: any(c.hygiene >= 85 and c.is_open() for c in g.food_cells()),
         weight=lambda g: 0.5, fire=ev_gourmet_blog),
    dict(id="BRIDAL_FAIR", cond=lambda g: g.has_venue() and g.bridal_boom <= 0,
         weight=lambda g: 0.6 + (1.0 if g.month() in (5, 6) else 0.0), fire=ev_bridal_fair),
    dict(id="CELEBRITY", cond=lambda g: any(c.kind == "SUITE" for c in g.rooms()),
         weight=lambda g: 0.4 + 0.6 * g.security(g.main), fire=ev_celebrity),
    dict(id="SAFE_AWARD",
         cond=lambda g: g.guard_count() >= 2 and g.min_security() >= 0.5,
         weight=lambda g: 0.5, fire=ev_safe_award),
    dict(id="PRICE_WAR", cond=lambda g: g.rival is not None and g.rival["war"] <= 0,
         weight=lambda g: 0.7, fire=ev_price_war),
    dict(id="RIVAL_SCANDAL", cond=lambda g: g.rival is not None,
         weight=lambda g: 0.3, fire=ev_rival_scandal),
    dict(id="POACHING",
         cond=lambda g: g.rival is not None and any(
             s.post is not None and s.skill >= 2 for s in g.staff),
         weight=lambda g: 0.5, fire=ev_poaching),
    dict(id="REVIEW_SITE",
         cond=lambda g: len(g.reviews) >= 15 and (review_avg20(g) >= 4.0 or
                                                  review_avg20(g) < 2.6),
         weight=lambda g: 0.7, fire=ev_review_site),
    dict(id="CRIME_WAVE", cond=lambda g: len(g.rooms()) >= 6 and g.crime_wave <= 0,
         weight=lambda g: 0.5, fire=ev_crime_wave),
]


class EventManager:
    def __init__(self):
        self.last = {}
        self.history = []

    def note(self, g, popup):
        self.history.append((g.day, popup["title"]))
        self.history = self.history[-20:]

    def roll(self, g):
        if random.random() > EVENT_CHANCE:
            return None
        cands = [e for e in EVENTS
                 if g.day - self.last.get(e["id"], -99) >= EVENT_COOLDOWN and e["cond"](g)]
        if not cands:
            return None
        ws = [max(0.0, e["weight"](g)) for e in cands]
        if sum(ws) <= 0:
            return None
        e = random.choices(cands, weights=ws)[0]
        self.last[e["id"]] = g.day
        popup = e["fire"](g)
        self.note(g, popup)
        return popup
