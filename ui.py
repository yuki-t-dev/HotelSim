# ============================================================
# ui.py  -  Pyxel front-end (input, menus, drawing)   Japanese UI
#
#   Scenes:
#     "title" : title screen (new game / continue)
#     "game"  : the hotel.  Two views:
#               "floor" : top-down floor plan of one building
#               "site"  : site map (lots / buildings / outdoor walkers)   M key
#   Text: Japanese BDF font (ASCII 6px, others 10px, line 12px).
#   Menu lines may contain "\t" to split into columns (Menu.cols).
# ============================================================
import math
import os
import sys
import weakref

from data import (W, H, LINE_H, MY, MB, PANEL_W, SITE_BTN_H, FLOOR_Y0, FLOOR_BTN_H,
                  CORR_TOP, CORR_BOT, CORR_Y, SX0, SW, COLS, SLOTS, TOP_Y0, TOP_Y1,
                  BOT_Y0, BOT_Y1, DOOR_W, STAIR_X, LOBBY_RESERVED,
                  FACILITIES, BUILDINGS, SITE_BUILD, BUILD_ORDER, ROLES, GUEST_TYPES,
                  BREAK_RULES, STAR_GOALS, FLOOR_LIMIT, FONT_FILES,
                  HYGIENE_WARN, HYGIENE_DANGER, DEEP_CLEAN_COST,
                  SITE_COLS, SITE_ROWS, LOT_GAP, LOT_X0, LOT_W,
                  TRAITS, LOT_FACILITIES, WEATHERS, OCEAN_PRICE, PRICE_STEP,
                  ROOM_KINDS, ROOM_TAG, CAMERA_COST, JUNE_PAY, ROUTES, ROUTE_ORDER, BATH_T,
                  DIFFICULTY, DIFF_ORDER, SAVE_SLOTS, HOLD_LABEL, HOLD_COLOR, UPGRADES,
                  KIOSK_UPKEEP, CONCIERGE_UPKEEP, LUNCH_T, OUTSIDE_COLOR,
                  clamp, slot_rect, cell_rect, t_to_clock, text_width, lot_rect, lot_dist)
from game import Game, VERSION
from model import Guest, Staff
import bookings as bk
import resort as rs
import shops as sh
import leisure as ls
import art
from data import POOL_T, NIGHT_POOL_T, POOL_OPEN, LEISURE_COLOR, DAYPASS, GYM_FEE
from data import SHOPPER_COLOR, BRANDS, BRAND_ORDER, TENANT_LEAVE
from data import LOT_Y0, LOT_H

STATE_LABEL = {"standby": "待機", "go_post": "移動中", "post": "勤務中", "work": "作業中",
               "go_rest": "休憩へ", "rest": "休憩中", "go_room": "移動中"}
FAC_SHORT = {spec["label"]: spec.get("short", spec["label"]) for spec in FACILITIES.values()}
MENU_W = min(W - 8, 420)                 # STEP 14: menus stay readable on the wide screen
MENU_X = (W - MENU_W) // 2
ROKUYO_COL = {"大安": 8, "友引": 9, "先勝": 7, "先負": 7, "赤口": 13, "仏滅": 5}
HERE = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(HERE, "saves")

# tutorial: (text, condition(app) -> bool)
TUTORIAL = [
    ("空き枠（＋）をクリックして客室を3室に",
     lambda a: len(a.g.rooms()) >= 3),
    ("0Fのフロントをクリックし2人目を雇おう",
     lambda a: a.g.post_count(("DESK",)) >= 2),
    ("人のアイコンで、スタッフの様子を見よう",
     lambda a: "staff" in a.g.tut_flags),
    ("カレンダーで天気と六曜を確認しよう",
     lambda a: "cal" in a.g.tut_flags),
    ("値札のアイコンで、部屋の料金を決めよう",
     lambda a: "price" in a.g.tut_flags),
    ("地図のアイコンで、敷地全体を見てみよう",
     lambda a: "site" in a.g.tut_flags),
    ("★のアイコンで、次の目標を確認しよう",
     lambda a: "goals" in a.g.tut_flags),
    ("右下の一時停止ボタンで、時間を止められます",
     lambda a: "pause" in a.g.tut_flags),
    ("歯車のアイコンから、いつでもセーブできます",
     lambda a: "sys" in a.g.tut_flags),
]
# toolbar button that each tutorial step points at (None = a place on the map)
TUT_TARGET = [None, None, "staff", "cal", "price", "site", "goals", "pause", "sys"]

# ------------------------------------------------------------
# STEP 15: toolbar (mouse) - icons are 10x10 pixel art drawn in draw_icon()
# ------------------------------------------------------------
TB_Y = H - 22               # toolbar row
TB_H = 20
TB_W = 22
TOOLS = [                   # key, label (tooltip; keyboard shortcuts stay hidden)
    ("staff", "スタッフ"), ("book", "予約台帳"), ("bank", "銀行"),
    ("cal", "カレンダー"), ("price", "料金"), ("goals", "目標"),
    ("review", "口コミ"), ("site", "敷地マップ"), ("sys", "システム"),
]
SPEEDS = [("pause", "一時停止", 0), ("x1", "ふつう", 1), ("x2", "はやい", 2),
          ("x4", "とてもはやい", 4)]


class Menu:
    def __init__(self, title, items, info=None, on_hover=None, modal=False, cols=None):
        self.title = title
        self.items = items
        self.info = info or []
        self.sel = 0
        self.on_hover = on_hover
        self.modal = modal
        self.cols = cols or [0]
        self.top = 0                    # STEP 15: first visible item (scrolling)
        self.fix_sel()

    def fix_sel(self):
        self.sel = clamp(self.sel, 0, max(0, len(self.items) - 1))
        if self.items and not self.items[self.sel][1]:
            for i, it in enumerate(self.items):
                if it[1]:
                    self.sel = i
                    break


def h_rect(c):
    return cell_rect(c)[3]


def demand_mark(m):
    return "+++" if m >= 1.3 else "++" if m >= 1.1 else "+" if m >= 0.9 else "-"


def hyg_color(h):
    return 8 if h < HYGIENE_DANGER else 9 if h < HYGIENE_WARN else 11


def sec_color(s):
    return 11 if s >= 0.5 else 9 if s >= 0.25 else 8


def load_font(pyxel):
    if not hasattr(pyxel, "Font"):
        sys.exit("Pyxel 2.2 以降が必要です:  pip install -U pyxel")
    for name in FONT_FILES:
        path = os.path.join(HERE, name)
        if os.path.exists(path):
            return pyxel.Font(path)
    sys.exit("フォント %s が見つかりません。main.py と同じフォルダに置いてください。"
             % FONT_FILES[0])


# ------------------------------------------------------------
# save files
# ------------------------------------------------------------
def slot_path(slot):
    name = "autosave.sav" if slot == 0 else "slot%d.sav" % slot
    return os.path.join(SAVE_DIR, name)


def write_save(g, slot):
    os.makedirs(SAVE_DIR, exist_ok=True)
    with open(slot_path(slot), "wb") as fp:
        fp.write(g.save_data())


def read_slot_meta(slot):
    p = slot_path(slot)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "rb") as fp:
            return Game.read_meta(fp.read())
    except Exception:
        return {"broken": True}


def load_slot(slot):
    with open(slot_path(slot), "rb") as fp:
        return Game.load_data(fp.read())


def slot_label(slot):
    name = "オート" if slot == 0 else "スロット%d" % slot
    m = read_slot_meta(slot)
    if m is None:
        return name + "\t（空き）", False
    if m.get("broken"):
        return name + "\t（読めません）", False
    return "%s\t%d日目 ★%d %s　評判%.1f　$%d" % (
        name, m["day"], m["star"], m["diff"], m["rep"], m["cash"]), True


class App:
    def __init__(self):
        import pyxel
        self.px = pyxel
        pyxel.init(W, H, title="PIXEL HOTEL " + VERSION, fps=30)
        pyxel.mouse(True)
        self.font = load_font(pyxel)
        self.overflow = []
        self.scene = "title"
        self.g = None
        self.menus = []
        self.frame = 0
        self.last_mouse = (-1, -1)
        self.preview = None
        self.open_title()
        pyxel.run(self.update, self.draw)

    # ---------------- scenes ----------------
    def open_title(self):
        self.scene = "title"
        self.menus = []
        self.open(self.menu_title())

    def start_game(self, g):
        self.g = g
        self.scene = "game"
        self.vb = g.main
        self.vf = 0
        self.mode = "floor"
        self.cx = 2
        self.cy = 0
        self.lot = self.vb.lot
        self.speed = 2
        self.paused = False
        self.menus = []
        self.preview = None
        self.motion = weakref.WeakKeyDictionary()   # agent -> [x, y, face, moved_frame]

    def restart(self):
        self.open_title()

    # ---------------- text ----------------
    def tx(self, x, y, s, col):
        self.px.text(x, y, s, col, self.font)

    def tx_center(self, cx, y, s, col):
        self.tx(cx - text_width(s) // 2, y, s, col)

    def tx_vertical(self, x, y, s, col):
        for i, ch in enumerate(s):
            self.tx(x, y + i * LINE_H, ch, col)

    def tx_shadow(self, x, y, s, col, sh=0):
        self.tx(x + 1, y + 1, s, sh)
        self.tx(x, y, s, col)

    # ---------------- view ----------------
    def set_floor(self, f):
        self.vf = clamp(f, 0, self.vb.floors - 1)

    def set_building(self, b, f=None):
        self.vb = b
        self.mode = "floor"
        self.lot = b.lot
        self.set_floor(self.vf if f is None else f)

    def toggle_site(self):
        if self.mode == "site":
            self.mode = "floor"
        else:
            self.mode = "site"
            self.lot = self.vb.lot
            self.flag("site")

    def flag(self, name):
        if self.g is not None:
            self.g.tut_flags.add(name)

    # ---------------- menus ----------------
    def open(self, m):
        self.menus.append(m)

    def close(self):
        if self.menus:
            self.menus.pop()

    def refresh(self, builder):
        sel = self.menus[-1].sel if self.menus else 0
        self.close()
        m = builder()
        m.sel = sel
        m.fix_sel()
        self.open(m)

    # ---------------- title / system menus (STEP 11) ----------------
    def menu_title(self):
        items = [("はじめから", True, lambda: self.open(self.menu_new_game()))]
        any_save = any(read_slot_meta(s) and not read_slot_meta(s).get("broken")
                       for s in range(SAVE_SLOTS + 1))
        items.append(("つづきから", any_save, lambda: self.open(self.menu_load(back=True))))
        items.append(("おわる", True, self.px.quit))
        m = Menu("", items, modal=True)
        m.title_screen = True
        return m

    def menu_new_game(self):
        state = {"tut": True}

        def build():
            items = []
            for k in DIFF_ORDER:
                d = DIFFICULTY[k]
                items.append(("%s\t資金$%d　%s" % (d["label"], d["cash"], d["text"]), True,
                              lambda k=k: self.start_game(Game(difficulty=k,
                                                               tutorial=state["tut"]))))
            items.append(("チュートリアル：%s" % ("あり" if state["tut"] else "なし"), True,
                          lambda: (state.update(tut=not state["tut"]), self.refresh(build))))
            items.append(("もどる", True, self.close))
            return Menu("難易度を選んでください", items, ["難易度はゲーム中に変えられません"],
                        cols=[0, 70])
        return build()

    def menu_load(self, back=False):
        items = []
        for s in range(SAVE_SLOTS + 1):
            label, ok = slot_label(s)
            items.append((label, ok, lambda s=s: self.do_load(s)))
        items.append(("もどる", True, self.close))
        return Menu("ロード", items, ["セーブした日の朝から再開します"], cols=[0, 70])

    def do_load(self, slot):
        try:
            g = load_slot(slot)
        except Exception as e:
            if self.g:
                self.g.log("ロードに失敗しました（%s）" % e.__class__.__name__)
            return
        self.start_game(g)

    def menu_save(self):
        g = self.g

        def save(s):
            try:
                write_save(g, s)
                g.log("スロット%dにセーブしました（%d日目の朝）" % (s, g.day))
            except Exception as e:
                g.log("セーブに失敗しました（%s）" % e.__class__.__name__)
            self.menus.clear()

        items = []
        for s in range(1, SAVE_SLOTS + 1):
            label, _ = slot_label(s)
            items.append((label, True, lambda s=s: save(s)))
        items.append(("もどる", True, self.close))
        when = ("今日の朝（%d日目 6:00）の状態を保存します" % g.day if g._snap is not None
                else "1日目は今の状態を保存します（2日目からは朝の状態）")
        return Menu("セーブ", items, [when, "毎朝、オートセーブもされます"], cols=[0, 70])

    def menu_system(self):
        g = self.g
        self.flag("sys")

        def toggle_tut():
            g.tutorial = not g.tutorial
            if g.tutorial and g.tut_step >= len(TUTORIAL):
                g.tut_step = 0
            self.refresh(self.menu_system)

        items = [("セーブ", True, lambda: self.open(self.menu_save())),
                 ("ロード", True, lambda: self.open(self.menu_load())),
                 ("チュートリアル：%s" % ("表示中" if g.tutorial else "非表示"), True,
                  toggle_tut),
                 ("操作説明", True, lambda: self.open(self.menu_help())),
                 ("タイトルへ戻る（セーブしていない進行は失われます）", True, self.open_title),
                 ("閉じる", True, self.close)]
        info = ["難易度：%s　%d日目" % (g.diff["label"], g.day)]
        return Menu("システム", items, info)

    def menu_help(self):
        info = ["左クリック：選ぶ　右クリック／枠の外：戻る",
                "空き枠（＋）：建設　部屋や施設：スタッフ配置など",
                "左の階ボタン／ホイール：階を移動",
                "廊下をクリック：防犯カメラ・巡回の設定",
                "下のアイコン：スタッフ・予約・銀行・暦・料金・目標",
                "　　　　　　　口コミ・敷地・システム",
                "右下のボタン：一時停止と速度　上の数字もクリック可",
                "マウスを乗せると、人や部屋の情報が出ます"]
        return Menu("操作説明", [("閉じる", True, self.close)], info)

    # ---------------- common menu helpers ----------------
    def demolish_item(self, c):
        g = self.g
        why = g.demolish_block(c)
        if why:
            return ("撤去できません（%s）" % why, False, None)
        return ("撤去して空きにする（+$%d）" % g.demolish_refund(c), True,
                lambda: (g.demolish(c), self.menus.clear()))

    def patrol_item(self, b):
        post = ("PATROL", b)
        return ("巡回する警備員\t%d/3" % self.g.post_count(post), True,
                lambda: self.open(self.menu_post(post, "GUARD", "%sを巡回する警備員" % b.name)()))

    def menu_floor(self):
        g = self.g
        b = self.vb
        items = []
        for f in range(b.floors - 1, -1, -1):
            cam = "◎" if f in b.cams else "　"
            if f > g.max_floor(b):
                txt = "%dF\t未開放" % f
            elif b.is_main() and f == 0:
                txt = "0F%s\tロビー　待ち%d人　フロント%d人" % (
                    cam, len(g.desk_queue), g.post_count(("DESK",)))
            else:
                s = g.floor_stats(b, f)
                txt = "%dF%s\t客室%d　宿泊中%d　要清掃%d　清掃係%d" % (
                    f, cam, s["rooms"], s["occ"], s["dirty"], s["cleaners"])
            items.append((txt, True, lambda f=f: (self.set_floor(f), self.close())))
        f = self.vf
        can = f <= g.max_floor(b) and f not in b.cams and g.cash >= CAMERA_COST
        items.append(("この階(%dF)に防犯カメラ（$%d）" % (f, CAMERA_COST), can,
                      lambda: (g.add_camera(b, f), self.refresh(self.menu_floor))))
        n = len([x for x in range(g.max_floor(b) + 1) if x not in b.cams])
        items.append(("全階に防犯カメラ（$%d）" % (CAMERA_COST * n),
                      n > 0 and g.cash >= CAMERA_COST * n,
                      lambda: (g.add_cameras_all(b), self.refresh(self.menu_floor))))
        items.append(self.patrol_item(b))
        items.append(("敷地マップへ", True, lambda: (self.close(), self.toggle_site())))
        info = ["◎＝防犯カメラあり　%sの防犯レベル %d%%" % (b.name, g.security(b) * 100)]
        m = Menu("%s：階を移動・防犯" % b.name, items, info, cols=[0, 34])
        m.sel = b.floors - 1 - self.vf
        return m

    def menu_build(self, b, f, s):
        g = self.g
        kinds = BUILD_ORDER
        items = []
        for k in kinds:
            spec = FACILITIES[k]
            ok, why = g.can_build(b, f, s, k)
            extra = why
            if ok:
                if spec["category"] == "food":
                    extra = "%s %s%s" % (spec["meal"], t_to_clock(spec["serve"]),
                                         "・昼可" if "lunch_price" in spec else "")
                elif spec["category"] == "room":
                    extra = "料金 $%d" % g.prices[k]
                elif k == "MEETING":
                    extra = "会議の予約・貸し出し"
                elif k == "BANQUET":
                    extra = "宴会・披露宴"
                elif spec["category"] == "resort":
                    extra = "入浴 %s" % t_to_clock(BATH_T)
                elif k == "POOL":
                    extra = "夏に人気・監視員が必要"
                elif k == "GYM":
                    extra = "会員費・ビジネス客"
                elif k == "SHOP":
                    extra = "通りがかりの客に売る"
                elif k == "TENANT":
                    extra = "ブランド店に貸す（家賃）"
                elif k == "SECROOM":
                    extra = "防犯カメラの監視"
                elif spec["category"] == "wedding":
                    extra = {"SHRINE": "神前式", "YUINO": "結納", "DRESS": "花嫁の支度"}[k]
            txt = "%s\t[%d]\t$%d\t%s" % (spec["label"], spec["size"], spec["cost"], extra)
            items.append((txt, ok, lambda k=k: (g.build(b, f, s, k), self.close())))

        def hover(i):
            a = g.anchor_for(b, f, s, kinds[i])
            return (a, FACILITIES[kinds[i]]["size"]) if a is not None else None
        info = ["[ ]は使う枠数。食事処・婚礼施設は各1つまで"]
        if b.kind == "ANNEX":
            info = ["別館：客室・大浴場・スパ・売店・警備室・休憩室"]
        elif b.kind == "MALL":
            info = ["商業棟：飲食店・売店・テナント・警備室・休憩室"]
        m = Menu("%s %dFに建設" % (b.name, f), items, info, on_hover=hover,
                 cols=[0, 62, 86, 130])
        m.sel = 0
        return m

    def menu_post(self, post, role, title):
        g = self.g
        cols = [0, 24, 76, 112, 170]

        def build():
            items = []
            for st in g.staff:
                if st.post == post and st.role == role:
                    items.append(("－\t%s\t%s\t疲労%d%%\t%s" % (
                        st.name, st.stars(), st.fatigue, STATE_LABEL.get(st.state, "")), True,
                        lambda st=st: (g.unassign(st), self.refresh(build))))
            for st in g.staff:
                if st.role == role and st.post is None:
                    why = g.assign_block(st, post)
                    items.append(("＋\t%s\t%s\t疲労%d%%\t待機 %s" % (
                        st.name, st.stars(), st.fatigue, why), why == "",
                        lambda st=st: (g.assign(st, post), self.refresh(build))))
            for c in g.candidates:
                if c.role == role:
                    why = g.assign_block(c, post)
                    ok = why == "" and g.cash >= g.hire_fee(c)
                    items.append(("雇う\t%s\t%s\t契約$%d\t日給$%d %s" % (
                        c.name, c.stars(), g.hire_fee(c), c.wage(), why), ok,
                        lambda c=c: (g.hire(c, post), self.refresh(build))))
            if not items:
                items.append(("（今日の応募者はいません）", False, None))
            return Menu(title, items, ["－外す　＋配置する　雇う＝新しく採用"], cols=cols)
        return build

    def menu_room(self, c):
        g = self.g
        b, f = c.b, c.f
        post = ("FLOOR", b, f)
        state = {"clean": "空室（清掃済み）", "dirty": "空室（要清掃）",
                 "occupied": "宿泊中", "broken": "閉鎖中（修理待ち）"}[c.state]
        info = ["%s号室（%s）　%s" % (c.number(), c.label, state),
                "料金 $%d%s" % (g.room_price(c), "（海側 +%d%%）" % round(
                    (OCEAN_PRICE - 1) * 100) if g.is_ocean(c) else ""),
                "この階の清掃係：%d人" % g.post_count(post)]
        if c.guest is not None:
            gg = c.guest
            hw = {"ok": "", "swap": "（%sの代わり）" % FACILITIES[gg.want]["label"],
                  "upgrade": "（%sから無料アップグレード）" % FACILITIES[gg.want]["label"],
                  "downgrade": "（%s希望だった…）" % FACILITIES[gg.want]["label"]}[gg.how]
            who = ("新郎新婦" if getattr(gg, "couple", False) else
                   "有名人" if gg.celeb else GUEST_TYPES[gg.gtype]["label"])
            info.append("宿泊客：%s %d名　あと%d泊%s" % (who, gg.party, gg.nights, hw))
        h = g.hold_of(c)
        if h is not None:
            info.append("★ 予約で確保中：%s%s" % (
                HOLD_LABEL[h[0]], "（%s）" % h[1].title if h[0] in ("GROUP", "BRIDE") else ""))
        items = [("この階の清掃係を配置", True,
                  lambda: self.open(self.menu_post(post, "CLEANER",
                                                   "%s%dFの清掃係" % (b.prefix, f))()))]
        if h is None:
            items.append(("VIP用に空けておく（一般客を入れない）", True,
                          lambda: (g.toggle_player_hold(c), self.close())))
        elif h[0] == "PLAYER":
            items.append(("VIP用の確保を解除する", True,
                          lambda: (g.toggle_player_hold(c), self.close())))
        info += self.upgrade_lines(c)
        items.append(self.upgrade_item(c))
        items.append(self.demolish_item(c))
        return Menu("%s Lv%d（%s%dF）" % (c.label, c.lv, b.prefix, f), items, info)

    def menu_food(self, c):
        g = self.g
        post = ("FAC", c)

        def build():
            spec = c.spec
            roles = spec["roles"]
            fans = sum(1 for gg in g.guests
                       if gg.state in ("in_room", "to_room") and gg.pref == c.kind)
            status = "営業中" if c.is_open() else "休業中（あと%d日）" % c.closed_days
            hy = int(c.hygiene)
            warn = ("　危険！" if hy < HYGIENE_DANGER else
                    "　汚れ気味" if hy < HYGIENE_WARN else "")
            lunch = ("　ランチ %s" % t_to_clock(LUNCH_T)) if c.lunch else ""
            info = [
                "%s　%sの提供 %s%s" % (status, spec["meal"], t_to_clock(spec["serve"]), lunch),
                "衛生度 %d/100%s" % (hy, warn),
                "1食$%d　料理人1人で%d食　必要：料理人%s" % (
                    spec["price"], spec["per_cook"], "★" * spec["cook_skill"]),
                "この店が好きな宿泊客 %d組　本日 %d食" % (fans, c.served_today),
            ]
            if spec.get("text"):
                info.insert(0, spec["text"])
            plan = getattr(c, "out_plan", {})
            ol, od = g.outside_expect(c, "lunch"), g.outside_expect(c, "dinner")
            if od or ol or "lunch_price" in spec:
                info.append("外来客の見込み：%s夕食 約%d人（今日の予定 %s）" % (
                    "ランチ 約%d人・" % round(ol) if c.lunch else "", round(od),
                    "・".join("%s%d" % ({"lunch": "昼", "dinner": "夜"}[k], v)
                             for k, v in plan.items() if v) or "なし"))
            if c.kind == "BAR":
                info.append("夜は酔客の騒ぎが起きやすい。警備員がいると安心")
            if g.cheap_food_days > 0:
                info.append("格安業者：あと%d日（汚れ2倍）" % g.cheap_food_days)
            items = [
                ("料理人\t%d/%d" % (g.post_count(post, "COOK"), roles["COOK"]), True,
                 lambda: self.open(self.menu_post(post, "COOK", "%s：料理人" % c.label)())),
                ("清掃係\t%d/%d" % (g.post_count(post, "CLEANER"), roles["CLEANER"]), True,
                 lambda: self.open(self.menu_post(post, "CLEANER", "%s：清掃係" % c.label)())),
                ("徹底清掃（$%d・衛生度→100）" % DEEP_CLEAN_COST,
                 g.cash >= DEEP_CLEAN_COST and c.hygiene < 100,
                 lambda: (g.deep_clean(c), self.refresh(build))),
            ]
            if "lunch_price" in spec:
                items.append(("ランチ営業：%s（1食$%d・料理人の疲労が増える）" % (
                    "する" if c.lunch else "しない", spec["lunch_price"]), True,
                    lambda: (g.toggle_lunch(c), self.refresh(build))))
            items.append(self.demolish_item(c))
            return Menu("%s（%dF）" % (c.label, c.f), items, info, cols=[0, 50])
        return build

    # ---------------- STEP 19: shops / tenants ----------------
    def menu_shop(self, c):
        g = self.g
        info = [c.spec["text"],
                "本日 %d人が購入　売上 $%d" % (c.served_today, getattr(c, "sales_today", 0)),
                "よく売れる場所：本館0F（全員が通る）・商業棟",
                "客室の奥や行き止まりは、人が通らず売れません",
                "雨の日は傘（$10）がよく売れます"]
        return Menu("売店（%s%dF）" % (c.b.prefix, c.f),
                    [self.demolish_item(c), ("閉じる", True, self.close)], info)

    def menu_tenant(self, c):
        g = self.g

        def build():
            br = sh.brand_of(c)
            items = []
            if br:
                info = ["%s（%s）" % (br["label"], br["kind"]),
                        "家賃 $%d/日　VIP・有名人1組につき +$%d" % (br["rent"], br["bonus"]),
                        "条件：評判%d以上（今%.1f）" % (br["rep"], g.rep)]
                if c.tenant_warn:
                    info.append("!! 評判不足 %d日目（%d日で退去）" % (c.tenant_warn, TENANT_LEAVE))
                info.append("VIP・有名人と観光客の満足度が上がります")
                items.append(("契約を終了する（区画は空きに戻る）", True,
                              lambda: (sh.end_tenant(g, c), self.refresh(build))))
            else:
                info = ["空き区画です。条件を満たすブランドから、朝に入居の希望が届きます",
                        "ブランド\t家賃/日\t条件"]
                used = sh.taken(g)
                for k in BRAND_ORDER:
                    b = BRANDS[k]
                    conds = "・".join("%s%s" % ("○" if ok else "×", t)
                                     for t, ok in sh.brand_ok(g, k))
                    info.append("%s\t$%d\t%s%s" % (b["short"], b["rent"], conds,
                                                  "（入居済）" if k in used else ""))
                items.append(self.demolish_item(c))
            items.append(("閉じる", True, self.close))
            return Menu("テナント（%s%dF）" % (c.b.prefix, c.f), items, info, cols=[0, 64, 112])
        return build

    def menu_secroom(self, c):
        g = self.g
        post = ("FAC", c)

        def build():
            cams = sum(len(b.cams) for b in g.buildings)
            watching = len(g.guards_on(post))
            info = [c.spec["text"],
                    "モニター監視：%s" % ("中（カメラの効果が最大）" if watching else
                                       "誰もいない（カメラの効果は弱い）"),
                    "防犯カメラ：全%d台（設置は各建物の階メニュー F）" % cams]
            for b in g.buildings:
                if not b.fixed():
                    info.append("%s　防犯レベル %d%%　巡回%d人" % (
                        b.name, g.security(b) * 100, g.post_count(("PATROL", b))))
            items = [("監視する警備員\t%d/2" % g.post_count(post, "GUARD"), True,
                      lambda: self.open(self.menu_post(post, "GUARD", "警備室：監視")())),
                     self.patrol_item(c.b),
                     self.demolish_item(c)]
            return Menu("警備室（%s%dF）" % (c.b.prefix, c.f), items, info, cols=[0, 110])
        return build

    # ---------------- STEP 17: upgrades ----------------
    def upgrade_item(self, c, after=None):
        g = self.g
        nxt, cost = g.upgrade_info(c)
        if nxt is None:
            return ("改装：最大レベル（Lv%d）" % c.lv, False, None)
        why = g.upgrade_block(c)
        label = "Lv%d→%d %s（$%d）%s" % (c.lv, c.lv + 1, nxt["label"], cost,
                                        "" if not why else "　" + why)
        return (label, why == "", lambda: (g.upgrade(c), after() if after else self.close()))

    def upgrade_lines(self, c):
        table = UPGRADES.get(self.g.upg_key(c))
        if not table:
            return []
        out = []
        for lv in range(2, len(table) + 1):
            mark = "○" if c.lv >= lv else "・"
            out.append("%sLv%d %s：%s" % (mark, lv, table[lv - 1]["label"], table[lv - 1]["text"]))
        return out

    def menu_front(self):
        g = self.g

        def build():
            nxt, cost = g.desk_upgrade_info()
            info = ["フロント係 %d人　待ち %d組" % (g.post_count(("DESK",)), len(g.desk_queue)),
                    "設備：%s" % ("・".join(UPGRADES["FRONT"][lv]["label"]
                                         for lv in range(1, g.desk_lv)) or "なし")]
            for lv in (2, 3):
                spec = UPGRADES["FRONT"][lv - 1]
                info.append("%sLv%d %s（★%d〜）：%s" % ("○" if g.desk_lv >= lv else "・", lv,
                                                    spec["label"], lv, spec["text"]))
            if g.desk_lv >= 2:
                info.append("維持費 $%d/日" % ((KIOSK_UPKEEP if g.desk_lv >= 2 else 0) +
                                             (CONCIERGE_UPKEEP if g.desk_lv >= 3 else 0)))
            items = [("フロント係を配置・雇う", True,
                      lambda: self.open(self.menu_post(("DESK",), "FRONT",
                                                       "フロント（最大3人）")()))]
            if nxt is None:
                items.append(("フロントは最大レベルです", False, None))
            else:
                need = g.desk_lv + 1
                why = ("要★%d" % need if g.star < need else
                       "資金不足" if g.cash < cost else "")
                items.append(("Lv%d→%d %s（$%d）%s" % (g.desk_lv, g.desk_lv + 1, nxt["label"],
                                                      cost, "　" + why if why else ""),
                              why == "", lambda: (g.upgrade_desk(), self.refresh(build))))
            return Menu("フロント（Lv%d）" % g.desk_lv, items, info)
        return build

    def menu_resort(self, c):
        g = self.g
        post = ("FAC", c)

        def build():
            hy = int(c.hygiene)
            warn = ("　汚れがひどい！" if hy < HYGIENE_DANGER else
                    "　汚れ気味" if hy < HYGIENE_WARN else "")
            info = [c.spec["text"],
                    "入浴 %s　定員%d人　本日 %d人" % (t_to_clock(BATH_T), c.spec["cap"],
                                                 c.served_today),
                    "衛生度 %d/100%s" % (hy, warn)]
            if c.kind == "ONSEN":
                info.append("露天風呂：%s" % ("あり（眺めで満足度UP）" if rs.open_air(c)
                                              else "なし（海側・森の別館に作ると露天に）"))
                info.append("冬は入浴する客が増えます")
            items = [
                ("清掃係\t%d/%d" % (g.post_count(post, "CLEANER"), c.spec["roles"]["CLEANER"]),
                 True, lambda: self.open(self.menu_post(post, "CLEANER",
                                                       "%s：清掃係" % c.label)())),
                ("徹底清掃（$%d・衛生度→100）" % DEEP_CLEAN_COST,
                 g.cash >= DEEP_CLEAN_COST and c.hygiene < 100,
                 lambda: (g.deep_clean(c), self.refresh(build))),
            ]
            if c.kind == "ONSEN":
                info += self.upgrade_lines(c)
                items.append(self.upgrade_item(c, lambda: self.refresh(build)))
            items.append(self.demolish_item(c))
            title = "%s Lv%d（%s%dF）" % (c.label, c.lv, c.b.prefix, c.f) if c.kind == "ONSEN" \
                else "%s（%s%dF）" % (c.label, c.b.prefix, c.f)
            return Menu(title, items, info, cols=[0, 50])
        return build

    # ---------------- STEP 20: pool / gym ----------------
    def menu_leisure(self, c):
        g = self.g
        post = ("FAC", c)

        def build():
            hy = int(c.hygiene)
            info = [c.spec["text"], "衛生度 %d/100" % hy]
            items = []
            if c.kind == "POOL":
                m = ls.pool_season_mult(g, c)
                state = ("営業中" if ls.pool_open(g, c) else
                         "休業中（%d日）" % c.closed_days if not c.is_open() else
                         "今日は閉鎖（冬・悪天候）")
                info.insert(1, "%s　%s～%s（混雑のピーク %s）%s" % (
                    state, t_to_clock(POOL_OPEN[0]), t_to_clock(POOL_OPEN[1]),
                    t_to_clock(POOL_T), "　夜 %s" % t_to_clock(NIGHT_POOL_T)
                    if ls.night_pool(c) else ""))
                plan = getattr(c, "out_plan", {})
                info.append("今日の人気 x%.1f　外来の予定 %d人%s　本日 %d人" % (
                    m, plan.get("day", 0), "（夜 %d人）" % plan.get("night", 0)
                    if ls.night_pool(c) else "", c.served_today))
                lg = len(ls.lifeguards(g, c))
                info.append("監視員：%s" % ("%d人（安全）" % lg if lg else
                                         "!! いません（事故の危険）"))
                items.append(("監視員（警備員）\t%d/1" % g.post_count(post, "GUARD"), True,
                              lambda: self.open(self.menu_post(post, "GUARD",
                                                               "プール：監視員")())))
            else:
                info.insert(1, "会員 %d人 / 上限 %d人　会費 $%d/人・日（今夜 +$%d）" % (
                    int(g.gym_members), ls.gym_cap(c), GYM_FEE,
                    int(g.gym_members) * GYM_FEE))
                info.append("会員は評判で増減。駅前に土地があると+20%")
                info.append("汚れたままだと会員が辞めていきます")
            items.append(("清掃係\t%d/1" % g.post_count(post, "CLEANER"), True,
                          lambda: self.open(self.menu_post(post, "CLEANER",
                                                           "%s：清掃係" % c.label)())))
            items.append(("徹底清掃（$%d・衛生度→100）" % DEEP_CLEAN_COST,
                          g.cash >= DEEP_CLEAN_COST and c.hygiene < 100,
                          lambda: (g.deep_clean(c), self.refresh(build))))
            info += self.upgrade_lines(c)
            items.append(self.upgrade_item(c, lambda: self.refresh(build)))
            items.append(self.demolish_item(c))
            return Menu("%s Lv%d（%s%dF）" % (c.label, c.lv, c.b.prefix, c.f), items, info,
                        cols=[0, 110])
        return build

    # ---------------- bookings ----------------
    def menu_ledger(self):
        g = self.g

        def build():
            items = []
            for b in bk.open_bookings(g):
                ready = all(ok for _, ok in bk.requirements(g, b))
                items.append(("%d日目\t%s\t%s\t%s\t%d名" % (
                    b.day, g.rokuyo(b.day), "○" if ready else "×", b.title, b.people), True,
                    lambda b=b: self.open(self.menu_booking(b, build))))
            if not items:
                items.append(("（予約はありません）", False, None))
            info = ["○＝今の状態で準備OK　×＝足りないものあり",
                    "打診は★2以上で、朝に届きます（最大%d件）" % bk.MAX_BOOKINGS]
            return Menu("予約台帳", items, info, cols=[0, 46, 80, 94, 270])
        return build

    def menu_booking(self, b, parent):
        g = self.g

        def do_cancel():
            bk.cancel(g, b)
            self.close()
            self.refresh(parent)

        info = ["%d日目（%d月・%s曜・%s）　%s名" % (
            b.day, g.month(b.day), g.weekday_label(b.day), g.rokuyo(b.day), b.people)]
        if b.day == g.day:
            info[0] += "　【本日】"
        if b.kind == "WEDDING":
            info.append("天気予報：%s" % WEATHERS[g.weather_at(b.day)]["label"]
                        if b.day <= g.day + 7 else "天気予報：まだわかりません")
        for text, ok in bk.requirements(g, b):
            info.append("%s %s" % ("○" if ok else "×", text))
        info.append("報酬 $%d　失敗時の違約金 $%d" % (b.pay, b.penalty))
        if b.rooms:
            info.append("当日は客室%d室を団体客に優先します" % b.rooms)
        items = [("キャンセルする（-$%d・評判-1）" % (b.penalty // 2), b.day > g.day, do_cancel),
                 ("閉じる", True, self.close)]
        return Menu(b.title, items, info)

    def menu_meeting(self, c):
        g = self.g
        today = [b for b in bk.today_bookings(g) if c in b.rooms_used]
        if today:
            use = "本日：%s" % today[0].title
        elif c.rented:
            use = "本日：貸し会議室として利用中"
        else:
            use = "本日：空き"
        info = [use, "平日は空いていれば自動で貸し出し（$%d）" % bk.RENTAL_PRICE,
                "カンファレンスの予約に必要です（%s～）" % t_to_clock(bk.MEET_T)]
        return Menu("会議室（%dF）" % c.f,
                    [self.demolish_item(c), ("閉じる", True, self.close)], info)

    def menu_banquet(self, c):
        g = self.g
        post = ("FAC", c)

        def build():
            spec = c.spec
            roles = spec["roles"]
            nxt = [b for b in bk.open_bookings(g) if b.banquet]
            hy = int(c.hygiene)
            warn = ("　危険！" if hy < HYGIENE_DANGER else
                    "　汚れ気味" if hy < HYGIENE_WARN else "")
            info = [
                ("営業中" if c.is_open() else "休業中（あと%d日）" % c.closed_days) +
                "　披露宴 %s／宴会 %s" % (t_to_clock(bk.RECEPTION_T), t_to_clock(spec["serve"])),
                "衛生度 %d/100%s" % (hy, warn),
                "料理人1人で%d食　今の配置で%d食" % (spec["per_cook"], bk.banquet_capacity(g)),
                ("次の予約：%d日目 %s %d食" % (nxt[0].day, nxt[0].short(), nxt[0].people))
                if nxt else "次の予約：なし",
                "披露宴では引き出物の紛失に注意（本館の防犯レベル）",
            ]
            items = [
                ("料理人\t%d/%d" % (g.post_count(post, "COOK"), roles["COOK"]), True,
                 lambda: self.open(self.menu_post(post, "COOK", "宴会場：料理人")())),
                ("清掃係\t%d/%d" % (g.post_count(post, "CLEANER"), roles["CLEANER"]), True,
                 lambda: self.open(self.menu_post(post, "CLEANER", "宴会場：清掃係")())),
                ("徹底清掃（$%d・衛生度→100）" % DEEP_CLEAN_COST,
                 g.cash >= DEEP_CLEAN_COST and c.hygiene < 100,
                 lambda: (g.deep_clean(c), self.refresh(build))),
                self.demolish_item(c),
            ]
            return Menu("宴会場（%dF）" % c.f, items, info, cols=[0, 50])
        return build

    def menu_wedding_fac(self, c):
        g = self.g
        today = [b for b in bk.today_bookings(g) if c in b.cells_used]
        info = [c.spec.get("text", "")]
        if c.kind == "CHAPEL_HALL":
            info = [BUILDINGS["CHAPEL"]["text"], "挙式 %s　→　宴会場で披露宴 %s" % (
                t_to_clock(bk.CEREMONY_T), t_to_clock(bk.RECEPTION_T))]
            info.append("渡り廊下：%s" % ("あり" if c.b.walkway else "なし（雨の日は濡れる）"))
            info.append("隣の庭園：%s" % ("あり（報酬+15%）" if g.chapel_garden() else "なし"))
        elif c.kind == "SHRINE":
            info.append("挙式 %s　→　宴会場で披露宴 %s" % (
                t_to_clock(bk.CEREMONY_T), t_to_clock(bk.RECEPTION_T)))
        if c.kind in ("CHAPEL_HALL", "SHRINE"):
            info.append("挙式の依頼が届く確率：1日%d%%" % round(bk.wedding_chance(g) * 100))
            if g.star < 2:
                info.append("!! ★2になると挙式の依頼が届き始めます")
            if bk.banquet_hall(g) is None:
                info.append("!! 宴会場がないため「挙式のみ」の依頼（報酬控えめ）")
            if bk.one(g, "DRESS") is None:
                info.append("!! 衣装室がないと、挙式の評価が下がります")
        info.append("6月はジューンブライド：依頼が増え、報酬+%d%%" % round((JUNE_PAY - 1) * 100))
        info.append("本日：%s" % (today[0].title if today else "予約なし"))
        nxt = [b for b in bk.open_bookings(g) if b.kind in ("WEDDING", "YUINO")]
        if nxt:
            nb = nxt[0]
            info.append("次の婚礼：%d日目（%s）%s %d名%s" % (
                nb.day, g.rokuyo(nb.day), nb.short(), nb.people,
                "" if nb.banquet or nb.kind != "WEDDING" else "・挙式のみ"))
        items = []
        if c.kind != "CHAPEL_HALL":
            items.append(self.demolish_item(c))
        items.append(("閉じる", True, self.close))
        return Menu("%s" % c.label, items, info)

    # ---------------- site ----------------
    def trait_lines(self, lot):
        t = TRAITS[self.g.trait(lot)]
        return ["特徴【%s】%s" % (t["label"], t["text"])]

    def menu_lot(self, lot):
        g = self.g
        b = g.building_at(lot)
        if b is not None:
            return self.menu_building(b)
        if lot in g.lot_fac:
            return self.menu_lotfac(lot)
        price = g.land_price(lot)
        dist = lot_dist(lot, g.main.lot)
        if lot in g.lots:
            items = []
            for kind in SITE_BUILD:
                spec = BUILDINGS[kind]
                ok, why = g.can_build_building(lot, kind)

                def do_build(kind=kind):
                    nb = g.build_building(lot, kind)
                    self.close()
                    if nb:
                        self.set_building(nb, 0)
                items.append(("%sを建てる（$%d）" % (spec["label"], spec["cost"]) +
                              ("" if ok else "　" + why), ok, do_build))
            for k, fs in LOT_FACILITIES.items():
                ok2, why2 = g.can_build_lotfac(lot, k)
                items.append(("%sを作る（$%d）" % (fs["label"], fs["cost"]) +
                              ("" if ok2 else "　" + why2), ok2,
                              lambda k=k: (g.build_lotfac(lot, k), self.close())))
            items.append(("閉じる", True, self.close))
            info = self.trait_lines(lot) + [
                "本館から%d区画" % dist,
                "別館：%s" % BUILDINGS["ANNEX"]["text"],
                "商業棟：%s" % BUILDINGS["MALL"]["text"],
                "チャペル：%s" % BUILDINGS["CHAPEL"]["text"],
                "庭園：%s" % LOT_FACILITIES["GARDEN"]["text"],
                "駐車場：%s" % LOT_FACILITIES["PARKING"]["text"]]
            return Menu("空き地（%s）" % TRAITS[g.trait(lot)]["label"], items, info)
        ok, why = g.can_buy(lot)

        def do_buy():
            g.buy_lot(lot)
            self.close()
        info = self.trait_lines(lot) + [
            "価格 $%d（本館から%d区画）" % (price, dist), "隣り合う区画から順に買い広げます"]
        label = "購入する（$%d）" % price + ("" if ok else "　" + why)
        return Menu("売り地（%s）" % TRAITS[g.trait(lot)]["label"],
                    [(label, ok, do_buy), ("閉じる", True, self.close)], info)

    def menu_building(self, b):
        g = self.g

        def enter():
            self.close()
            self.set_building(b, 0 if self.vb is not b else self.vf)
        info = self.trait_lines(b.lot)
        if b.kind != "CHAPEL":
            occ, n, dirty = g.building_stats(b)
            info.append("客室 %d室（宿泊中 %d・要清掃 %d）" % (n, occ, dirty))
            bonus = g.garden_bonus(b)
            if bonus:
                info.append("隣の庭園：宿泊客の満足度 +%.1f" % bonus)
            info.append("防犯レベル %d%%（巡回%d人・カメラ%d/%d階%s）" % (
                g.security(b) * 100, g.post_count(("PATROL", b)), len(b.cams),
                g.max_floor(b) + 1, "・監視中" if g.monitored() else ""))
        else:
            info.append(BUILDINGS["CHAPEL"]["text"])
            if g.chapel_garden():
                info.append("隣に庭園：挙式の報酬 +15%")
        items = [("建物に入る", True, enter)]
        if not b.fixed():
            items.append(self.patrol_item(b))
            n = len([x for x in range(g.max_floor(b) + 1) if x not in b.cams])
            if n:
                items.append(("全階に防犯カメラ（$%d）" % (CAMERA_COST * n),
                              g.cash >= CAMERA_COST * n,
                              lambda: (g.add_cameras_all(b), self.close())))
        if not b.is_main():
            if b.walkway:
                info.append("渡り廊下あり：雨・雪でも濡れずに本館と行き来")
            else:
                info.append("渡り廊下なし：雨の日は客が濡れて不満、雪は移動が遅い")
                cost = g.walkway_cost(b)
                items.append(("渡り廊下を作る（$%d）" % cost, g.cash >= cost,
                              lambda: (g.build_walkway(b), self.close())))
        items.append(("閉じる", True, self.close))
        return Menu(b.name, items, info, cols=[0, 110])

    def menu_lotfac(self, lot):
        g = self.g
        k = g.lot_fac[lot]
        fs = LOT_FACILITIES[k]
        info = self.trait_lines(lot) + [fs["text"], "維持費 $%d/日" % fs["upkeep"]]
        if k == "PARKING":
            info.append("来客 x%.2f（駐車場は2つまで有効）" % g.parking_mult())
        refund = int(fs["cost"] * 0.25)
        return Menu(fs["label"], [("撤去する（+$%d）" % refund, True,
                                   lambda: (g.remove_lotfac(lot), self.close())),
                                  ("閉じる", True, self.close)], info)

    # ---------------- prices / goals / reviews ----------------
    def menu_price(self):
        g = self.g
        self.flag("price")

        def build():
            def ch(kind, sign):
                return lambda: (g.change_price(kind, sign), self.refresh(build))
            items = []
            for k in ROOM_KINDS:
                lab = FACILITIES[k]["label"]
                items.append(("%s\t+$%d" % (lab, PRICE_STEP[k]), True, ch(k, 1)))
                items.append(("%s\t-$%d" % (lab, PRICE_STEP[k]), True, ch(k, -1)))
            n = {k: sum(1 for c in g.rooms() if c.kind == k) for k in ROOM_KINDS}
            info = ["種類\t料金\t適正\t部屋数\t人気（ビジ/観光）"]
            wb, wt = g.want_weights("BUSINESS"), g.want_weights("TOURIST")
            sb, st = sum(wb.values()), sum(wt.values())
            for k in ROOM_KINDS:
                if k == "SUITE":
                    pop = "%d%%/%d%%" % (g.suite_want_p("BUSINESS") * 100,
                                         g.suite_want_p("TOURIST") * 100)
                else:
                    pop = "%d%%/%d%%" % (wb[k] / sb * 100, wt[k] / st * 100)
                info.append("%s\t$%d\t$%d\t%d室\t%s" % (FACILITIES[k]["label"], g.prices[k],
                                                    g.fair(k), n[k], pop))
            if g.hot_demand():
                info.append("★ 今日は値上げの好機！ 泊まりたい客%d組／空き%d室" % (
                    round(g.demand_raw), g.demand_cap))
            info.append("海側の部屋は+%d%%。適正より高いと来客と満足度が下がる" %
                        round((OCEAN_PRICE - 1) * 100))
            info.append("希望の部屋がない→同格に交換／上位に無料UP／下位で不満")
            return Menu("宿泊料金", items, info,
                        cols=[0, 64, 110, 156, 196])
        return build

    def menu_goals(self):
        g = self.g
        self.flag("goals")
        info = []
        if g.star < 3:
            info.append("まずは★%dを目指しましょう：" % (g.star + 1))
            info.append("　" + STAR_GOALS[g.star + 1][3])
        elif g.route:
            info.append("達成済み：「%s」" % ROUTES[g.route]["label"])
        else:
            info.append("★4は、次のどれか1つを達成すると手に入ります")
        for k in ROUTE_ORDER:
            rt = ROUTES[k]
            done = rs.route_done(g, k)
            info.append("%s【%s】%s %d%%" % ("◎" if done else "・", rt["short"], rt["label"],
                                          rs.route_progress(g, k) * 100))
            parts = []
            for label, cur, need, text in rs.route_conditions(g, k):
                parts.append("%s%s %s" % ("○" if cur >= need else "×", label, text))
            info.append("　" + "　".join(parts[:2]))
            if len(parts) > 2:
                info.append("　" + "　".join(parts[2:]))
        return Menu("目標（★4への4つの道）", [("閉じる", True, self.close)], info)

    def menu_reviews(self):
        g = self.g
        info = []
        if g.reviews:
            info.append("直近%d件の平均 %.2f　（来客 x%.2f）" % (
                min(20, len(g.reviews)), rs.review_avg(g), rs.review_mult(g)))
        else:
            info.append("まだ口コミはありません（チェックアウトで投稿されます）")
        for day, st, who, text in reversed(g.reviews[-14:]):
            info.append("%d日目\t%s\t%s\t%s" % (day, "★" * st + "☆" * (5 - st), who, text))
        return Menu("口コミ", [("閉じる", True, self.close)], info, cols=[0, 46, 100, 150])

    # ---------------- staff / bank / calendar / report ----------------
    def menu_staff(self):
        g = self.g
        self.flag("staff")

        def build():
            items = []
            for st in g.staff:
                txt = "%s\t%s\t%s\t疲労%d%%\t%s\t$%d" % (
                    st.name, ROLES[st.role]["label"], st.stars(), st.fatigue,
                    g.post_name(st.post), st.wage())
                items.append((txt, True, lambda st=st: self.open(self.menu_staff_one(st, build))))
            if not items:
                items.append(("（スタッフがいません）", False, None))

            def rule():
                g.break_idx = (g.break_idx + 1) % len(BREAK_RULES)
                self.refresh(build)
            items.append(("休憩ルール：疲労%d%%で休憩（クリックで変更）" % g.break_rule(), True,
                          rule))
            return Menu("スタッフ一覧", items, cols=[0, 44, 92, 126, 176, 272])
        return build

    def menu_staff_one(self, st, parent):
        g = self.g

        def back():
            self.close()
            self.refresh(parent)

        def goto():
            self.menus.clear()
            if st.transit > 0 and st.trip is not None:
                self.mode = "site"
                return
            b, f = (st.dest if st.transit > 0 else (st.b, st.floor))
            self.set_building(b, f)

        items = [
            ("今すぐ休憩させる", st.post is not None and st.state != "rest",
             lambda: (g.send_rest(st, True), back())),
            ("配置を外す（待機）", st.post is not None, lambda: (g.unassign(st), back())),
            ("いる場所を表示", st.post is not None, goto),
            ("解雇する", True, lambda: (g.fire(st), back())),
        ]
        info = ["%s　%s %s　経験 %d" % (st.name, ROLES[st.role]["label"], st.stars(), st.exp),
                "疲労 %d%%　日給 $%d　配置 %s" % (st.fatigue, st.wage(), g.post_name(st.post))]
        if st.role == "GUARD":
            info.append("巡回：建物の各階を見回る／警備室：カメラを監視")
        return Menu(st.name, items, info)

    def menu_bank(self):
        g = self.g

        def build():
            room = g.credit_limit() - g.debt
            items = [
                ("$500 借りる", room >= 500, lambda: (g.borrow(500), self.refresh(build))),
                ("$2000 借りる", room >= 2000, lambda: (g.borrow(2000), self.refresh(build))),
                ("$500 返す", g.debt > 0 and g.cash > 0,
                 lambda: (g.repay(500), self.refresh(build))),
                ("全額返す", g.debt > 0 and g.cash > 0,
                 lambda: (g.repay(g.debt), self.refresh(build))),
            ]
            info = ["借入 $%d ／ 融資枠 $%d" % (g.debt, g.credit_limit()),
                    "金利 1日%.1f%%（今夜の利息 $%d）" % (
                        g.interest_rate() * 100, math.ceil(g.debt * g.interest_rate())),
                    "融資枠は★と評判で増えます", "枠を超えた状態が3晩続くと破産"]
            if g.over_limit_nights:
                info.append("!! 枠超え：%d/3晩" % g.over_limit_nights)
            return Menu("銀行", items, info)
        return build

    def menu_calendar(self):
        g = self.g
        self.flag("cal")
        info = ["日\t月\t曜\t六曜\t天気\t需要\tビジ/観光\t予約"]
        for d in range(g.day, g.day + 7):
            biz = int(g.biz_share(d) * 100)
            bs = bk.bookings_on(g, d)
            info.append("%d日目%s\t%d月\t%s\t%s\t%s\t%s\t%d/%d\t%s" % (
                d, "←" if d == g.day else "", g.month(d), g.weekday_label(d), g.rokuyo(d),
                WEATHERS[g.weather_at(d)]["label"],
                demand_mark(g.demand_mult(d) * WEATHERS[g.weather_at(d)]["demand"]),
                biz, 100 - biz, ("%s%d名" % (bs[0].short(), bs[0].people)) if len(bs) == 1
                else "・".join(b.short() for b in bs)))
        info.append("")
        info.append("今日の予想客数：約%d組（%s）" % (round(g.expected_guests()),
                                              g.season_label()))
        if g.hot_demand():
            info.append("★ 今日は泊まりたい客が部屋数を大きく上回っています")
        info.append("六曜：大安・友引は挙式の人気日、仏滅は不人気")
        info.append("6月はジューンブライド：挙式の依頼が増え、報酬+%d%%" %
                    round((JUNE_PAY - 1) * 100))
        if g.rival:
            r = g.rival
            info.append("%sライバル %s 評判%.1f（こちら%.1f）%s" % (
                "!! " if r["rep"] > g.rep else "", r["name"], r["rep"], g.rep,
                "　値下げ中" if r["war"] > 0 else ""))
        if g.crime_wave > 0:
            info.append("!! 近所で空き巣が多発中（あと%d日）" % g.crime_wave)
        if g.events.history:
            d, t = g.events.history[-1]
            info.append("最近の出来事：%d日目 %s" % (d, t.replace("イベント：", "")))
        return Menu("カレンダー（7日間・天気予報）", [("閉じる", True, self.close)], info,
                    cols=[0, 58, 84, 104, 132, 158, 186, 238])

    def menu_report(self):
        g = self.g
        r = g.report
        types = "　".join("%s %d" % (GUEST_TYPES[k]["label"], v) for k, v in r["types"].items())
        rb = " ".join("%s%d" % (ROOM_TAG[k], r["rooms_by"][k]) for k in ROOM_KINDS)
        info = [
            "%d月 %s曜日（%s）　天気：%s" % (r["month"], r["weekday_label"], r["rokuyo"],
                                       WEATHERS[r["weather"]]["label"]),
            "収入\t+$%d（うち食事 $%d）" % (r["income"], r["food"]),
            "支出\t給料 -$%d　維持費 -$%d　利息 -$%d" % (r["wages"], r["upkeep"],
                                                   r["interest"]),
            "宿泊客\t%d組（%s）" % (r["guests"], types),
            "部屋\t%s" % rb,
            "満室で断った %d組（機会損失$%d）　怒って帰った %d組" % (
                r["full"] + r.get("lost_busy", 0), r.get("lost_value", 0), r["angry_desk"]),
            "評判\t%.1f → %.1f" % (r["rep0"], r["rep1"]),
        ]
        if r.get("out") and (r["out"]["lunch"] or r["out"]["dinner"]):
            info.append("外来客\tランチ %d人・夕食 %d人（+$%d）" % (
                r["out"]["lunch"], r["out"]["dinner"], r.get("out_food", 0)))
        if r.get("shop") or r.get("rent"):
            info.append("お店\t売店 +$%d%s　家賃 +$%d%s" % (
                r.get("shop", 0), "（傘%d本）" % r["umbrella"] if r.get("umbrella") else "",
                r.get("rent", 0), "（VIP分 +$%d）" % r["rent_bonus"] if r.get("rent_bonus")
                else ""))
        if r.get("hungry"):
            info.append("食事\t満席で食べられなかった客 %d組（料理人を増やそう）" % r["hungry"])
        sc = r["sec"]
        if sc["prevented"] or sc["happened"]:
            info.append(("!! 防犯：未然に防いだ %d件　発生 %d件" if sc["happened"] else
                         "防犯\t未然に防いだ %d件　発生 %d件") % (sc["prevented"], sc["happened"]))
        hw = r["how"]
        if hw["downgrade"]:
            info.append("!! 希望外：無料UP %d　同格交換 %d　下位 %d" % (
                hw["upgrade"], hw["swap"], hw["downgrade"]))
        meals = "　".join("%s%d" % (FACILITIES[k]["short"], v)
                         for k, v in r["meals"].items() if v)
        if meals:
            info.append("食事\t" + meals)
        if r["resort"]:
            info.append("スパ\t+$%d" % r["resort"])
        if r.get("leisure") or r.get("gym"):
            info.append("プール等\tデイパス %d人 +$%d　ジム会員 %d人 +$%d" % (
                r.get("pool_out", 0), r.get("leisure", 0), r.get("gym_members", 0),
                r.get("gym", 0)))
        if r["reviews"]:
            info.append("口コミ\t今日%d件 平均%.1f（直近%.2f）" % (
                len(r["reviews"]), sum(r["reviews"]) / len(r["reviews"]), r["review_avg"]))
        if r["rival"]:
            info.append("ライバル\t評判 %.1f（こちら %.1f）" % (r["rival"]["rep"], r["rep1"]))
        if r["wet"]:
            info.append("!! 雨で濡れた客 %d組（渡り廊下で防げます）" % r["wet"])
        if r["rental"]:
            info.append("会議室\t貸し出し +$%d" % r["rental"])
        for title, result, amount in r["bookings"]:
            info.append("%s予約：%s %s$%d" % ("!! " if result == "失敗" else "", result,
                                             "+" if amount >= 0 else "-", abs(amount)))
        if r["poison"]:
            info.append("!! 食中毒：%d人が体調不良" % r["poison"])
        if r["overdraft"]:
            info.append("!! 資金不足で借入 $%d（手数料$100）" % r["overdraft"])
        if r["over"]:
            info.append("!! 借入が融資枠超え %d/3晩" % r["over"])
        if r["quits"]:
            info.append("退職（疲労）：" + "、".join(r["quits"]))
        if r.get("star_up") and r["star_up"] < 4:
            info.append("★★ ★%dに昇格！ ★★" % r["star_up"])
            if r.get("fair_up"):
                info.append("★ 適正価格が上がりました（シングル$%d）料金を見直そう" % r["fair_up"])
        info.append("明日：%s曜日 %s　需要%s" % r["next_label"])
        return Menu("%d日目の日報" % r["day"], [("次の日へ", True, self.close)], info,
                    cols=[0, 50])

    def menu_event(self, popup):
        g = self.g

        def chooser(fn):
            def cb():
                if fn:
                    fn(g)
                g.pending.remove(popup)
                self.close()
            return cb
        items = [(label, ok, chooser(fn)) for label, ok, fn in popup["choices"]]
        return Menu(popup["title"], items, popup["lines"], modal=True)

    # ---------------- update ----------------
    def update(self):
        px = self.px
        self.frame += 1
        if px.btnp(px.KEY_Q):
            px.quit()
        if self.scene == "title":
            if self.menus:
                self.update_menu(self.menus[-1])
            if self.scene == "title" and not self.menus:
                self.open(self.menu_title())
            return
        g = self.g
        if g.sec_flash:
            b, n = g.sec_flash
            g.sec_flash = (b, n - 1) if n > 1 else None
        g.popups = [(b, f, x, y, st, n - 1) for b, f, x, y, st, n in g.popups if n > 1]
        if g.confetti:
            g.confetti = (g.confetti[0], g.confetti[1] - 1) if g.confetti[1] > 1 else None
        if g.fire_fx:
            g.fire_fx = (g.fire_fx[0], g.fire_fx[1] - 1) if g.fire_fx[1] > 1 else None
        if g.cleared or g.bankrupt:
            if px.btnp(px.KEY_R) or px.btnp(px.MOUSE_BUTTON_RIGHT) or \
                    (g.bankrupt and px.btnp(px.MOUSE_BUTTON_LEFT)):
                self.open_title()
            elif g.cleared and (px.btnp(px.KEY_Z) or px.btnp(px.MOUSE_BUTTON_LEFT)):
                g.keep_playing()
            return
        self.update_tutorial()
        if not self.menus and g.pending:
            self.open(self.menu_event(g.pending[0]))
        if self.menus:
            self.update_menu(self.menus[-1])
            return
        self.preview = None
        if self.mode == "site":
            self.update_site_keys()
        else:
            self.update_floor_keys()
        if px.btnp(px.KEY_M):
            self.toggle_site()
        if px.btnp(px.KEY_A, 10, 3):
            g.change_price("SINGLE", -1)
        if px.btnp(px.KEY_D, 10, 3):
            g.change_price("SINGLE", 1)
        if px.btnp(px.KEY_P):
            self.open(self.menu_price()())
        if px.btnp(px.KEY_SPACE):
            if self.paused:
                self.paused = False
            else:
                self.speed = {1: 2, 2: 4, 4: 1}[self.speed]
        self.update_wheel()
        if px.btnp(px.KEY_B):
            g.break_idx = (g.break_idx + 1) % len(BREAK_RULES)
            g.log("休憩ルール：疲労%d%%で休憩" % g.break_rule())
        if px.btnp(px.KEY_H):
            self.open(self.menu_staff()())
        if px.btnp(px.KEY_L):
            self.open(self.menu_bank()())
        if px.btnp(px.KEY_C):
            self.open(self.menu_calendar())
        if px.btnp(px.KEY_K):
            self.open(self.menu_ledger()())
        if px.btnp(px.KEY_G):
            self.open(self.menu_goals())
        if px.btnp(px.KEY_V):
            self.open(self.menu_reviews())
        if px.btnp(px.KEY_TAB):
            self.open(self.menu_system())
        if px.btnp(px.MOUSE_BUTTON_LEFT):
            if not self.click_bars(px.mouse_x, px.mouse_y):
                self.on_click(px.mouse_x, px.mouse_y)
        if self.menus or self.paused:
            return
        for _ in range(self.speed):
            day = g.day
            g.tick()
            if g.day != day:
                self.autosave()
                self.open(self.menu_report())
                break
            if g.pending:
                break

    # ================================================================
    # STEP 15: mouse-only control (toolbar, clickable HUD, wheel, tooltips)
    # ================================================================
    def tool_rects(self):
        """[(key, label, x, y, w, h)] for the toolbar"""
        out = []
        x = 4
        for key, label in TOOLS:
            out.append((key, label, x, TB_Y, TB_W, TB_H))
            x += TB_W + 2
        x = W - 4 - len(SPEEDS) * (TB_W + 2) + 2
        for key, label, _ in SPEEDS:
            out.append((key, label, x, TB_Y, TB_W, TB_H))
            x += TB_W + 2
        return out

    def hud_rects(self):
        """clickable areas of the status bar: (key, x, y, w, h)"""
        return [("cal", 0, 0, 230, 13), ("goals", W - 96, 0, 96, 13),
                ("bank", 0, 13, 168, 13), ("price", 168, 13, 150, 13),
                ("goals", 0, 26, W, 13)]

    def run_tool(self, key):
        g = self.g
        if key == "staff":
            self.open(self.menu_staff()())
        elif key == "book":
            self.open(self.menu_ledger()())
        elif key == "bank":
            self.open(self.menu_bank()())
        elif key == "cal":
            self.open(self.menu_calendar())
        elif key == "price":
            self.open(self.menu_price()())
        elif key == "goals":
            self.open(self.menu_goals())
        elif key == "review":
            self.open(self.menu_reviews())
        elif key == "site":
            self.toggle_site()
        elif key == "sys":
            self.open(self.menu_system())
        elif key == "pause":
            self.paused = not self.paused
            self.flag("pause")
        else:
            self.speed = {"x1": 1, "x2": 2, "x4": 4}[key]
            self.paused = False
        _ = g

    @staticmethod
    def inside(mx, my, x, y, w, h):
        return x <= mx < x + w and y <= my < y + h

    def click_bars(self, mx, my):
        """toolbar / HUD clicks. True if handled"""
        for key, _, x, y, w, h in self.tool_rects():
            if self.inside(mx, my, x, y, w, h):
                self.run_tool(key)
                return True
        if my < MY:
            for key, x, y, w, h in self.hud_rects():
                if self.inside(mx, my, x, y, w, h):
                    self.run_tool(key)
                    return True
            return True
        if my >= MB:
            return True                          # log area: nothing to click
        return False

    def update_wheel(self):
        wheel = getattr(self.px, "mouse_wheel", 0)
        if not wheel:
            return
        if self.mode == "floor":
            self.set_floor(self.vf + (1 if wheel > 0 else -1))

    def notices(self):
        """toolbar keys that need attention (red dot)"""
        g = self.g
        out = set()
        for b in bk.open_bookings(g):
            if b.day <= g.day + 1 and not all(ok for _, ok in bk.requirements(g, b)):
                out.add("book")
        if any(s.fatigue >= 90 and s.post is not None for s in g.staff):
            out.add("staff")
        for b in g.buildings:
            for f in range(b.floors):
                st = g.floor_stats(b, f)
                if st["dirty"] and not st["cleaners"]:
                    out.add("staff")
        if g.over_limit_nights or g.debt > g.credit_limit() * 0.85:
            out.add("bank")
        if g.hot_demand():
            out.add("price")
        if g.reviews and rs.review_avg(g) < 2.8:
            out.add("review")
        if g.star >= 3 and not g.route and any(rs.route_done(g, k) for k in ROUTE_ORDER):
            out.add("goals")
        return out

    def draw_toolbar(self):
        px = self.px
        mx, my = px.mouse_x, px.mouse_y
        alerts = self.notices()
        tut = None
        g = self.g
        if g.tutorial and g.tut_step < len(TUT_TARGET) and not self.menus:
            tut = TUT_TARGET[g.tut_step]
        px.rect(0, TB_Y - 2, W, H - TB_Y + 2, 1)
        px.line(0, TB_Y - 2, W, TB_Y - 2, 5)
        for key, label, x, y, w, h in self.tool_rects():
            hot = self.inside(mx, my, x, y, w, h) and not self.menus
            on = (key == "pause" and self.paused) or \
                 (key in ("x1", "x2", "x4") and not self.paused and
                  self.speed == {"x1": 1, "x2": 2, "x4": 4}[key]) or \
                 (key == "site" and self.mode == "site")
            px.rect(x, y, w, h, 5 if (hot or on) else 0)
            px.rectb(x, y, w, h, 10 if on else (7 if hot else 13))
            self.draw_icon(key, x + (w - 10) // 2, y + (h - 10) // 2)
            if key in alerts and self.frame % 30 < 22:
                px.circ(x + w - 3, y + 2, 2, 8)
            if key == tut and self.frame % 20 < 14:
                px.rectb(x - 2, y - 2, w + 4, h + 4, 10)
                px.rectb(x - 1, y - 1, w + 2, h + 2, 9)
                ax = x + w // 2
                for i in range(4):                     # arrow above the button
                    px.line(ax - i, y - 9 + i, ax + i, y - 9 + i, 10)

    def draw_icon(self, key, x, y):
        """10x10 pixel-art icons"""
        px = self.px
        p = px.pset
        if key == "staff":                              # head + shoulders
            px.circ(x + 5, y + 3, 2, 15)
            px.rect(x + 1, y + 6, 9, 4, 12)
            p(x + 5, y + 6, 7)
        elif key == "book":                             # open notebook
            px.rect(x, y + 1, 4, 8, 7)
            px.rect(x + 6, y + 1, 4, 8, 7)
            px.rect(x + 4, y + 1, 2, 8, 4)
            for i in range(3):
                px.line(x + 1, y + 3 + i * 2, x + 2, y + 3 + i * 2, 13)
                px.line(x + 7, y + 3 + i * 2, x + 8, y + 3 + i * 2, 13)
        elif key == "bank":                             # pile of coins
            for i, (cx, cy) in enumerate(((3, 7), (7, 7), (5, 4))):
                px.circ(x + cx, y + cy, 2, 10)
                p(x + cx, y + cy, 9)
            p(x + 5, y + 1, 10)
        elif key == "cal":                              # tear-off calendar
            px.rect(x + 1, y + 1, 8, 8, 7)
            px.rect(x + 1, y + 1, 8, 2, 8)
            for i in range(3):
                for j in range(2):
                    p(x + 2 + i * 3, y + 5 + j * 2, 13)
        elif key == "price":                            # price tag
            px.rect(x + 2, y + 2, 7, 6, 10)
            p(x + 1, y + 4, 10)
            p(x + 1, y + 5, 10)
            p(x + 3, y + 4, 0)
            px.line(x + 5, y + 4, x + 7, y + 4, 4)
            px.line(x + 5, y + 6, x + 7, y + 6, 4)
        elif key == "goals":                            # star
            for dx, dy in ((4, 0), (5, 0), (4, 1), (5, 1), (3, 2), (4, 2), (5, 2), (6, 2)):
                p(x + dx, y + dy + 1, 10)
            px.rect(x + 1, y + 3, 8, 2, 10)
            px.rect(x + 2, y + 5, 6, 2, 10)
            px.rect(x + 2, y + 7, 2, 2, 10)
            px.rect(x + 6, y + 7, 2, 2, 10)
        elif key == "review":                           # speech bubble
            px.rect(x, y + 1, 10, 6, 7)
            p(x + 2, y + 7, 7)
            p(x + 2, y + 8, 7)
            for i in range(3):
                p(x + 2 + i * 3, y + 4, 13)
        elif key == "site":                             # map: lots + road
            px.rect(x, y, 10, 10, 11)
            px.line(x, y + 5, x + 9, y + 5, 13)
            px.line(x + 5, y, x + 5, y + 9, 13)
            px.rect(x + 1, y + 1, 3, 3, 7)
            px.rect(x + 6, y + 6, 3, 3, 8)
            px.rect(x + 1, y + 7, 3, 2, 12)
        elif key == "sys":                              # gear
            px.circ(x + 5, y + 5, 3, 13)
            for dx, dy in ((0, -4), (0, 4), (-4, 0), (4, 0), (-3, -3), (3, 3), (-3, 3), (3, -3)):
                p(x + 5 + dx, y + 5 + dy, 13)
            p(x + 5, y + 5, 0)
            px.circ(x + 5, y + 5, 1, 1)
        elif key == "pause":
            px.rect(x + 2, y + 1, 2, 8, 7)
            px.rect(x + 6, y + 1, 2, 8, 7)
        else:
            n = {"x1": 1, "x2": 2, "x4": 3}[key]
            w = 4
            x0 = x + (10 - (n * w + (n - 1))) // 2
            for k in range(n):
                for i in range(4):
                    px.line(x0 + k * (w + 1) + i, y + 1 + i, x0 + k * (w + 1) + i,
                            y + 8 - i, 7 if key != "x4" else 10)

    def tooltip_text(self, mx, my):
        """text for the thing under the mouse (or None)"""
        g = self.g
        for key, label, x, y, w, h in self.tool_rects():
            if self.inside(mx, my, x, y, w, h):
                return [label]
        if my < MY:
            names = {"cal": "クリック：カレンダー", "goals": "クリック：目標",
                     "bank": "クリック：銀行", "price": "クリック：料金"}
            for key, x, y, w, h in self.hud_rects():
                if self.inside(mx, my, x, y, w, h):
                    return [names[key]]
            return None
        if self.mode != "floor" or my >= MB or mx < PANEL_W:
            return None
        b, f = self.vb, self.vf
        best, bd = None, 7
        for a in g.guests + g.staff + g.visitors:
            if getattr(a, "state", "") == "gone" or not a.visible_in(b, f):
                continue
            if isinstance(a, Staff) and a.post is None:
                continue
            d = abs(a.x - mx) + abs(a.y - 2 - my)
            if d < bd:
                best, bd = a, d
        if isinstance(best, Guest):
            who = "有名人" if best.celeb else ("VIP" if best.vip else
                                              GUEST_TYPES[best.gtype]["label"] + "客")
            lines = ["%s %d名　%s希望" % (who, best.party, FACILITIES[best.want]["label"])]
            st = {"enter": "到着", "queue_desk": "フロント待ち %d%%" % min(
                99, best.desk_wait * 100 // max(1, int(g.patience(best)))),
                  "checkin": "チェックイン中", "to_room": "部屋へ移動中",
                  "in_room": "滞在中（あと%d泊）" % best.nights, "checkout": "お帰り",
                  "leaving": "お帰り"}.get(best.state, "")
            lines.append(st)
            if best.room is not None:
                lines.append("%s号室" % best.room.number())
            return lines
        if isinstance(best, Staff):
            return ["%s（%s %s）" % (best.name, ROLES[best.role]["label"], best.stars()),
                    "疲労%d%%　%s" % (best.fatigue, STATE_LABEL.get(best.state, ""))]
        if best is not None:
            return ["来客（%s）" % (best.cell.label if best.cell else "")]
        for s in range(b.nslots):
            x, y, w, h = slot_rect(s, b.cols)
            if not self.inside(mx, my, x, y, w, h):
                continue
            if b.is_main() and f == 0 and s in LOBBY_RESERVED:
                return ["フロント Lv%d　待ち%d組" % (g.desk_lv, len(g.desk_queue)),
                        "クリック：配置・設備の強化"]
            c = b.grid[f][s]
            if c is None:
                return ["空き枠　クリック：建設"] if f <= g.max_floor(b) else None
            if c.is_room():
                st = {"clean": "空室", "dirty": "要清掃", "occupied": "宿泊中",
                      "broken": "閉鎖中"}[c.state]
                lines = ["%s号室 %s%s　$%d" % (c.number(), c.label,
                                             " Lv%d" % c.lv if c.lv > 1 else "",
                                             g.room_price(c)), st]
                if g.hold_of(c) is not None:
                    lines.append("予約で確保：%s" % g.hold_label(c))
                return lines
            lines = [c.label]
            if c.kind == "TENANT":
                br = sh.brand_of(c)
                lines = [br["label"] if br else "テナント区画（空き）"]
                if br:
                    lines.append("家賃 $%d/日" % br["rent"])
            elif c.kind == "SHOP":
                lines.append("本日 %d人・$%d" % (c.served_today, getattr(c, "sales_today", 0)))
            if c.has_hygiene():
                lines.append("衛生度 %d" % c.hygiene)
            return lines
        return None

    def draw_tooltip(self):
        px = self.px
        mx, my = px.mouse_x, px.mouse_y
        lines = [l for l in (self.tooltip_text(mx, my) or []) if l]
        if not lines:
            return
        w = max(text_width(l) for l in lines) + 8
        h = len(lines) * LINE_H + 4
        x = clamp(mx + 8, 0, W - w)
        y = my - h - 4 if my > H // 2 else my + 12
        y = clamp(y, 0, H - h)
        px.rect(x, y, w, h, 0)
        px.rectb(x, y, w, h, 13)
        for i, l in enumerate(lines):
            self.tx(x + 4, y + 2 + i * LINE_H, l, 7 if i == 0 else 6)

    def autosave(self):
        try:
            write_save(self.g, 0)
        except Exception:
            pass

    def update_tutorial(self):
        g = self.g
        if not g.tutorial:
            return
        while g.tut_step < len(TUTORIAL) and TUTORIAL[g.tut_step][1](self):
            g.tut_step += 1
            if g.tut_step >= len(TUTORIAL):
                g.log("チュートリアル完了！ 良いホテル経営を！")
                g.tutorial = False

    def update_menu(self, m):
        px = self.px
        wheel = getattr(px, "mouse_wheel", 0)
        if wheel and not getattr(m, "title_screen", False) and len(m.items) > self.menu_rows(m):
            m.top = clamp(m.top - wheel, 0, len(m.items) - self.menu_rows(m))
            m.sel = clamp(m.sel, m.top, m.top + self.menu_rows(m) - 1)
        self.menu_mouse(m)
        if not self.menus or self.menus[-1] is not m:
            self.update_preview()
            return
        if px.btnp(px.KEY_UP, 10, 3):
            m.sel = (m.sel - 1) % max(1, len(m.items))
        if px.btnp(px.KEY_DOWN, 10, 3):
            m.sel = (m.sel + 1) % max(1, len(m.items))
        self.keep_visible(m)
        if px.btnp(px.KEY_Z) or px.btnp(px.KEY_RETURN):
            if m.items:
                label, ok, cb = m.items[m.sel]
                if ok and cb:
                    cb()
        if (px.btnp(px.KEY_X) or px.btnp(px.KEY_TAB)) and not m.modal and self.menus \
                and self.menus[-1] is m:
            self.close()
        self.update_preview()

    def update_floor_keys(self):
        px = self.px
        if px.btnp(px.KEY_LEFT, 10, 3):
            self.move_cursor(-1)
        if px.btnp(px.KEY_RIGHT, 10, 3):
            self.move_cursor(1)
        if px.btnp(px.KEY_UP, 10, 3):
            self.cy = 0
        if px.btnp(px.KEY_DOWN, 10, 3):
            self.cy = 1
        if px.btnp(px.KEY_W, 10, 3):
            self.set_floor(self.vf + 1)
        if px.btnp(px.KEY_S, 10, 3):
            self.set_floor(self.vf - 1)
        for f in range(self.vb.floors):
            if px.btnp(getattr(px, "KEY_%d" % f)):
                self.set_floor(f)
        if px.btnp(px.KEY_F):
            self.open(self.menu_floor())
        if px.btnp(px.KEY_Z):
            self.on_select()

    def update_site_keys(self):
        px = self.px
        lx, ly = self.lot
        if px.btnp(px.KEY_LEFT, 10, 3):
            lx -= 1
        if px.btnp(px.KEY_RIGHT, 10, 3):
            lx += 1
        if px.btnp(px.KEY_UP, 10, 3):
            ly -= 1
        if px.btnp(px.KEY_DOWN, 10, 3):
            ly += 1
        self.lot = (clamp(lx, 0, SITE_COLS - 1), clamp(ly, 0, SITE_ROWS - 1))
        if px.btnp(px.KEY_Z):
            self.open(self.menu_lot(self.lot))

    def update_preview(self):
        top = self.menus[-1] if self.menus else None
        self.preview = top.on_hover(top.sel) if top and top.on_hover else None

    # ---------------- menu geometry / mouse ----------------
    def menu_rows(self, m):
        """how many items fit on screen (STEP 15: long menus scroll)"""
        room = (H - 6 - 20 - len(m.info) * LINE_H - (4 if m.info else 0)) // LINE_H
        return max(3, room)

    def keep_visible(self, m):
        rows = self.menu_rows(m)
        if m.sel < m.top:
            m.top = m.sel
        elif m.sel >= m.top + rows:
            m.top = m.sel - rows + 1
        m.top = clamp(m.top, 0, max(0, len(m.items) - rows))

    def menu_rect(self, m):
        if getattr(m, "title_screen", False):
            h = 8 + len(m.items) * (LINE_H + 4)
            return W // 2 - 60, 176, 120, h, 180
        lines = len(m.info) + min(len(m.items), self.menu_rows(m))
        h = 20 + lines * LINE_H + (4 if m.info else 0)
        x, w = MENU_X, MENU_W
        y = clamp((H - h) // 2, 2, max(2, H - h - 2))
        if m.on_hover is not None:
            y = max(2, MB - h) if self.cy == 0 else MY
            y = clamp(y, 2, max(2, H - h - 2))
        iy = y + 18 + len(m.info) * LINE_H + (4 if m.info else 0)
        return x, y, w, h, iy

    def item_h(self, m):
        return LINE_H + 4 if getattr(m, "title_screen", False) else LINE_H

    def close_btn_rect(self, m):
        x, y, w, h, _ = self.menu_rect(m)
        return x + w - 14, y + 2, 12, 12

    def menu_item_at(self, m, mx, my):
        x, y, w, h, iy = self.menu_rect(m)
        if not (x + 2 <= mx < x + w - 2):
            return None
        d = my - iy + 1
        if d < 0:
            return None
        i = d // self.item_h(m)
        if getattr(m, "title_screen", False):
            return i if i < len(m.items) else None
        if i >= self.menu_rows(m):
            return None
        i += m.top
        return i if i < len(m.items) else None

    def menu_mouse(self, m):
        px = self.px
        mx, my = px.mouse_x, px.mouse_y
        moved = (mx, my) != self.last_mouse
        self.last_mouse = (mx, my)
        i = self.menu_item_at(m, mx, my)
        if moved and i is not None:
            m.sel = i
        if px.btnp(px.MOUSE_BUTTON_RIGHT):
            if not m.modal:
                self.close()
            return
        if not px.btnp(px.MOUSE_BUTTON_LEFT):
            return
        bx, by, bw, bh = self.close_btn_rect(m)
        x, y, w, h, _ = self.menu_rect(m)
        if not m.modal and bx <= mx < bx + bw and by <= my < by + bh:
            self.close()
        elif not (x <= mx < x + w and y <= my < y + h):
            if not m.modal:
                self.close()
        elif i is not None:
            m.sel = i
            label, ok, cb = m.items[i]
            if ok and cb:
                cb()

    def move_cursor(self, d):
        grid = self.vb.grid[self.vf]
        cols = self.vb.cols
        self.cx = clamp(self.cx, 0, cols - 1)
        row = self.cy * cols
        cur = grid[row + self.cx]
        nx = clamp(self.cx + d, 0, cols - 1)
        while cur is not None and grid[row + nx] is cur:
            if nx + d < 0 or nx + d >= cols:
                return
            nx += d
        nxt = grid[row + nx]
        if nxt is not None:
            nx = nxt.s % cols
        self.cx = nx

    def panel_buildings(self):
        return self.g.buildings[:7]

    def on_click(self, mx, my):
        if mx < PANEL_W:
            if MY <= my < MY + SITE_BTN_H:
                self.toggle_site()
                return
            i = (my - FLOOR_Y0) // FLOOR_BTN_H
            if my < FLOOR_Y0 or i < 0:
                return
            if self.mode == "site":
                bs = self.panel_buildings()
                if i < len(bs):
                    self.set_building(bs[i], 0)
            elif i < self.vb.floors:
                self.set_floor(self.vb.floors - 1 - i)
            return
        if self.mode == "site":
            for lx in range(SITE_COLS):
                for ly in range(SITE_ROWS):
                    x, y, w, h = lot_rect((lx, ly))
                    if x <= mx < x + w and y <= my < y + h:
                        self.lot = (lx, ly)
                        self.open(self.menu_lot(self.lot))
                        return
            return
        if CORR_TOP <= my < CORR_BOT and mx >= SX0:
            self.open(self.menu_floor())
            return
        b = self.vb
        for s in range(b.nslots):
            x, y, w, h = slot_rect(s, b.cols)
            if x <= mx < x + w and y <= my < y + h:
                self.cx, self.cy = s % b.cols, s // b.cols
                self.on_select()
                return

    def on_select(self):
        g = self.g
        b, f = self.vb, self.vf
        self.cx = clamp(self.cx, 0, b.cols - 1)
        s = self.cy * b.cols + self.cx
        if b.fixed():
            hall = b.grid[0][0]
            self.open(self.menu_wedding_fac(hall) if hall else
                      Menu(b.name, [("閉じる", True, self.close)], []))
            return
        if b.is_main() and f == 0 and s in LOBBY_RESERVED:
            self.open(self.menu_front()())
            return
        c = b.grid[f][s]
        if c is None:
            self.open(self.menu_build(b, f, s))
        elif c.is_room():
            self.open(self.menu_room(c))
        elif c.is_food():
            self.open(self.menu_food(c)())
        elif c.kind == "MEETING":
            self.open(self.menu_meeting(c))
        elif c.kind == "BANQUET":
            self.open(self.menu_banquet(c)())
        elif c.category == "wedding":
            self.open(self.menu_wedding_fac(c))
        elif c.category == "resort":
            self.open(self.menu_resort(c)())
        elif c.category == "leisure":
            self.open(self.menu_leisure(c)())
        elif c.category == "security":
            self.open(self.menu_secroom(c)())
        elif c.category == "shop":
            self.open(self.menu_shop(c))
        elif c.category == "tenant":
            self.open(self.menu_tenant(c)())
        elif c.category == "staff":
            info = ["席 %d/%d" % (len(c.seats), c.spec["seats"])] + [
                "%s　疲労%d%%" % (st.name, st.fatigue) for st in c.seats]
            self.open(Menu("休憩室（%s%dF）" % (b.prefix, f),
                           [self.demolish_item(c), ("閉じる", True, self.close)], info))

    # ---------------- draw ----------------
    def draw(self):
        px = self.px
        px.cls(0)
        if self.scene == "title":
            self.draw_title()
            if self.menus:
                self.draw_menu(self.menus[-1])
            return
        g = self.g
        if self.mode == "site":
            self.draw_site_panel()
            self.draw_site()
        else:
            self.draw_panel()
            self.draw_floor()
            self.draw_agents()
            self.draw_cursor()
        self.draw_hud()
        self.draw_log()
        if g.tutorial and not self.menus and g.tut_step < len(TUTORIAL):
            self.draw_tutorial()
        if not self.menus and not g.cleared and not g.bankrupt:
            self.draw_tooltip()
        if self.menus:
            self.draw_menu(self.menus[-1])
        if g.cleared:
            rt = ROUTES[g.route]
            avg = rs.review_avg(g) if g.reviews else 0
            self.draw_banner("★★★★ ホテル完成！ ★★★★",
                             ["「%s」として認められました！" % rt["label"],
                              "難易度：%s　経過日数：%d日" % (g.diff["label"], g.day),
                              "評判：%.1f　口コミ平均：%.1f（%d件）" % (g.rep, avg,
                                                                len(g.reviews)),
                              "純資産：$%d　借入：$%d" % (g.net_worth(), g.debt),
                              "スタッフ：%d人　建物：%d棟" % (len(g.staff), len(g.buildings)),
                              "",
                              "クリック：このまま経営を続ける",
                              "右クリック：タイトルへ"], 10)
        elif g.bankrupt:
            self.draw_banner("破産…", ["銀行にホテルを差し押さえられた。", "%d日目" % g.day,
                                     "クリック：タイトルへ（ロードでやり直せます）"], 8)

    def draw_title(self):
        px = self.px
        f = self.frame
        # night sky gradient
        for i, col in enumerate((1, 1, 1, 5, 5)):
            px.rect(0, i * 34, W, 34, col)
        for i in range(40):                                  # stars
            sx = (i * 73) % W
            sy = (i * 37) % 120
            if (f // 15 + i) % 5:
                px.pset(sx, sy, 7 if i % 3 else 10)
        mx = W - 70
        px.circ(mx, 34, 12, 10)                              # moon
        px.circ(mx + 6, 30, 11, 1)
        # sea
        px.rect(0, 170, W, H - 170, 1)
        for i in range(0, W, 12):
            wy = 176 + ((i // 12 + f // 10) % 3) * 6
            px.line(i, wy, i + 6, wy, 5)
        # hotel
        bx, by, bw, bh = W // 2 - 64, 66, 128, 104
        px.rect(bx, by, bw, bh, 13)
        px.rect(bx, by - 6, bw, 6, 2)
        px.rect(bx + 50, by - 18, 28, 12, 2)
        for row in range(6):
            for colx in range(8):
                lit = (row * 7 + colx * 3 + f // 40) % 5 != 0
                px.rect(bx + 6 + colx * 15, by + 6 + row * 15, 9, 9, 10 if lit else 1)
        px.rect(bx + 54, by + bh - 16, 20, 16, 4)
        px.rect(bx + 56, by + bh - 14, 16, 14, 9)
        # sign
        px.rect(bx + 30, by - 34, 68, 14, 0)
        px.rectb(bx + 30, by - 34, 68, 14, 10 if (f // 20) % 2 else 8)
        self.tx_center(W // 2, by - 33, "HOTEL", 10)
        # title
        self.tx_shadow(W // 2 - text_width("ピクセルホテル") // 2, 8, "ピクセルホテル", 10, 2)
        self.tx_center(W // 2, 22, "～ ★4への道 ～", 7)
        self.tx(2, H - 12, VERSION, 13)


    def draw_tutorial(self):
        px = self.px
        g = self.g
        text, _ = TUTORIAL[g.tut_step]
        x, y, w, h = PANEL_W + 2, MB - 30, W - PANEL_W - 4, 28
        px.rect(x, y, w, h, 0)
        px.rectb(x, y, w, h, 10 if self.frame % 40 < 30 else 9)
        self.tx(x + 4, y + 2, "ヒント %d/%d（歯車のアイコンで非表示にできます）" % (
            g.tut_step + 1, len(TUTORIAL)), 10)
        self.tx(x + 4, y + 14, text, 7)

    def draw_site_button(self, line1, line2, active):
        px = self.px
        px.rect(1, MY + 1, PANEL_W - 3, SITE_BTN_H - 2, 3 if active else 1)
        px.rectb(1, MY + 1, PANEL_W - 3, SITE_BTN_H - 2, 11)
        self.tx(4, MY + 1, line1, 10)
        self.tx(4, MY + 12, line2, 7)

    def draw_panel(self):
        px = self.px
        g = self.g
        b = self.vb
        blink = self.frame % 20 < 12
        self.draw_site_button(b.name, "敷地へ", False)
        for f in range(b.floors - 1, -1, -1):
            y = FLOOR_Y0 + (b.floors - 1 - f) * FLOOR_BTN_H
            locked = f > g.max_floor(b)
            cur = f == self.vf
            px.rect(1, y + 1, PANEL_W - 3, FLOOR_BTN_H - 2, 5 if cur else (0 if locked else 1))
            px.rectb(1, y + 1, PANEL_W - 3, FLOOR_BTN_H - 2, 10 if cur else 5)
            self.tx(4, y, "%dF" % f, 13 if locked else (10 if cur else 7))
            if locked:
                self.tx(4, y + 10, "未開放", 13)
                continue
            if f in b.cams:
                px.rect(17, y + 3, 4, 3, 13)
                px.pset(18, y + 4, 8 if g.monitored() else 0)
            if b.fixed():
                today = [x for x in bk.today_bookings(g) if x.kind == "WEDDING"
                         and x.style == "CHAPEL"]
                self.tx(4, y + 10, "挙式あり" if today else "礼拝堂", 8 if today else 7)
                continue
            s = g.floor_stats(b, f)
            if s["food_closed"]:
                self.tx(PANEL_W - 12, y, "X", 8)
            elif s["food_low"] < HYGIENE_WARN:
                col = 8 if s["food_low"] < HYGIENE_DANGER else 9
                if blink or s["food_low"] >= HYGIENE_DANGER:
                    self.tx(PANEL_W - 12, y, "H", col)
            if b.is_main() and f == 0:
                q = len(g.desk_queue)
                self.tx(4, y + 10, "待%d" % q, 8 if q > 5 else 7)
                self.tx(28, y + 10, "受%d" % g.post_count(("DESK",)), 9)
                continue
            self.tx(24, y, "%d/%d" % (s["occ"], s["rooms"]), 10)
            if s["dirty"]:
                col = 8 if (s["cleaners"] == 0 and blink) else 15
                self.tx(4, y + 10, "汚%d" % s["dirty"], col)
            self.tx(28, y + 10, "清%d" % s["cleaners"], 11)
            if s["dirty"] and s["cleaners"] == 0 and blink:
                self.tx(PANEL_W - 12, y + 10, "!", 8)
            elif s["broken"]:
                self.tx(PANEL_W - 12, y + 10, "X", 8)

    def draw_site_panel(self):
        px = self.px
        g = self.g
        self.draw_site_button("敷地", "建物へ", True)
        for i, b in enumerate(self.panel_buildings()):
            y = FLOOR_Y0 + i * FLOOR_BTN_H
            cur = b is self.vb
            px.rect(1, y + 1, PANEL_W - 3, FLOOR_BTN_H - 2, 5 if cur else 1)
            px.rectb(1, y + 1, PANEL_W - 3, FLOOR_BTN_H - 2, 10 if cur else 5)
            self.tx(4, y, b.name, 10 if cur else 7)
            if b.fixed():
                self.tx(4, y + 10, "婚礼", 14)
                continue
            if b.kind == "MALL":
                n_shop = sum(1 for c in g.cells() if c.b is b and
                             c.category in ("shop", "tenant", "food"))
                self.tx(4, y + 10, "店%d" % n_shop, 9)
                s = g.security(b)
                self.tx(34, y + 10, "防%d" % round(s * 10), sec_color(s))
                continue
            occ, n, dirty = g.building_stats(b)
            self.tx(4, y + 10, "%d/%d" % (occ, n), 10)
            s = g.security(b)
            self.tx(34, y + 10, "防%d" % round(s * 10), sec_color(s))

    def draw_floor(self):
        """floor view with time-of-day lighting (STEP 12)"""
        px = self.px
        g = self.g
        ph = art.phase(g.t)
        art.set_tint(px, art.IN_TINT[ph])
        try:
            self.draw_floor_body()
        finally:
            art.reset_tint(px)
        if self.vf <= g.max_floor(self.vb):
            self.draw_floor_lights(ph)

    def draw_cell_lit(self, c):
        """sleeping guests' rooms go dark after 22:00"""
        g = self.g
        if c.is_room() and c.state == "occupied" and art.late(g.t):
            art.set_tint(self.px, art.SLEEP_TINT)
            self.draw_cell(c)
            art.set_tint(self.px, art.IN_TINT[art.phase(g.t)])
        else:
            self.draw_cell(c)

    def draw_floor_lights(self, ph):
        px = self.px
        g = self.g
        b, f = self.vb, self.vf
        if ph in ("DUSK", "NIGHT"):
            # ceiling lamps along the corridor
            for x in range(SX0 + 20, W - 16, 48):
                art.glow(px, x, CORR_Y, 4, 6 if ph == "NIGHT" else 15)
                px.pset(x, CORR_Y, 10)
        for c in g.floor_cells(b, f):
            if not (c.is_room() and c.state == "occupied"):
                continue
            _, _, bx, by = c.bed_pt()
            if art.late(g.t):
                if self.frame % 60 < 45:
                    self.tx(bx + 8, by - 6, "zZ", 6)
            elif ph in ("DUSK", "NIGHT"):
                art.glow(px, bx - 14, by, 4, 10)        # bedside lamp
                px.pset(bx - 14, by, 7)

    def draw_floor_body(self):
        px = self.px
        g = self.g
        b, f = self.vb, self.vf
        x0 = PANEL_W
        px.rect(x0, MY, W - x0, MB - MY, 4 if b.is_main() else 5)
        if f > g.max_floor(b):
            px.rect(x0 + 2, MY + 2, W - x0 - 4, MB - MY - 4, 0)
            need = min(s for s, lim in FLOOR_LIMIT.items() if lim >= f)
            cx = (x0 + W) // 2
            self.tx_center(cx, CORR_Y - 14, "%dF　未開放" % f, 13)
            self.tx_center(cx, CORR_Y + 2, "★%dで開放" % need, 13)
            return
        ccol = 6 if f == 0 else 13
        px.rect(x0 + 2, CORR_TOP, W - x0 - 2, CORR_BOT - CORR_TOP, ccol)
        for xx in range(x0 + 22, W, 8):
            px.line(xx, CORR_Y, xx + 3, CORR_Y, 7 if f == 0 else 6)
        sx, sy, sw, sh = x0 + 2, TOP_Y0, SX0 - x0 - 3, TOP_Y1 - TOP_Y0
        px.rect(sx, sy, sw, sh, 13)
        for yy in range(sy + 3, sy + sh, 5):
            px.line(sx + 1, yy, sx + sw - 2, yy, 5)
        self.tx_vertical(sx + (sw - 10) // 2, sy + 4, "階段", 1)
        px.rect(STAIR_X - 4, TOP_Y1 - 1, 9, 2, ccol)
        bx, by, bw, bh = x0 + 2, BOT_Y0, SX0 - x0 - 3, BOT_Y1 - BOT_Y0
        px.rect(bx, by, bw, bh, 1)
        self.tx_vertical(bx + (bw - 10) // 2, by + 4, "倉庫", 5)
        if b.fixed():
            self.draw_plaza()
        for s in range(b.nslots):
            if b.is_main() and f == 0 and s in LOBBY_RESERVED:
                continue
            c = b.grid[f][s]
            if c is not None and c.s != s:
                continue
            if c is None:
                if b.fixed():
                    continue
                x, y, w, h = slot_rect(s, b.cols)
                px.rect(x, y, w, h, 1)
                px.rectb(x + 2, y + 2, w - 4, h - 4, 5)
                self.tx_center(x + w // 2, y + h // 2 - 6, "+", 5)
            else:
                self.draw_cell_lit(c)
        if b.is_main() and f == 0:
            self.draw_lobby()
        if b.cols * SW + SX0 < W - 100 and not b.fixed():
            self.draw_floor_info(b, f)                 # STEP 14: right-side info panel
        if f == 0:
            px.rect(W - 4, CORR_TOP - 2, 4, CORR_BOT - CORR_TOP + 4, 3)
            px.rect(W - 14, CORR_TOP + 2, 9, CORR_BOT - CORR_TOP - 4, 11)
        if f in b.cams:
            self.draw_cameras()
        if g.sec_flash and g.sec_flash[0] is b and self.frame % 10 < 6:
            px.rectb(PANEL_W + 1, MY + 1, W - PANEL_W - 2, MB - MY - 2, 11)

    # ---- STEP 14: info panel next to a narrow building (main building) ----
    def info_box(self, x, y, w, h, title, lines):
        px = self.px
        px.rect(x, y, w, h, 1)
        px.rectb(x, y, w, h, 5)
        px.rect(x + 1, y + 1, w - 2, 11, 5)
        self.tx(x + 4, y + 1, title, 10)
        yy = y + 13
        for text, col in lines:
            if yy + 11 > y + h:
                break
            self.tx(x + 4, yy, text, col)
            yy += LINE_H

    def draw_floor_info(self, b, f):
        g = self.g
        x0 = SX0 + b.cols * SW + 4
        w = W - x0 - 4
        cells = g.floor_cells(b, f)
        top, bot = [], []
        if b.is_main() and f == 0:
            fronts = g.post_count(("DESK",))
            q = len(g.desk_queue)
            left = sum(1 for a in g.arrivals if a[0] >= g.t)
            top.append(("フロント %d人　待ち %d組" % (fronts, q), 8 if q > 5 else 7))
            top.append(("今日の到着予定 あと%d組" % left, 6))
            top.append(("今日の宿泊 %d組" % g.d_guests, 6))
            top.append(("今夜の空室 %d室" % g.sellable_rooms(), 11))
            if g.d_lost_full:
                top.append(("満室で断った %d組" % g.d_lost_full, 9))
            title = "0F ロビー"
        else:
            s = g.floor_stats(b, f)
            title = "%s%dF" % (b.prefix, f)
            top.append(("客室 %d室　宿泊中 %d" % (s["rooms"], s["occ"]), 7))
            top.append(("要清掃 %d　清掃係 %d人" % (s["dirty"], s["cleaners"]),
                        8 if s["dirty"] and not s["cleaners"] else 7))
            kinds = {}
            for c in cells:
                if c.is_room():
                    kinds[c.kind] = kinds.get(c.kind, 0) + 1
            if kinds:
                top.append((" ".join("%s%d" % (ROOM_TAG[k], kinds[k]) for k in ROOM_KINDS
                                     if k in kinds), 6))
            if s["broken"]:
                top.append(("閉鎖中の部屋 %d" % s["broken"], 8))
            nh = sum(1 for c in cells if c.is_room() and g.hold_of(c) is not None)
            if nh:
                top.append(("予約で確保 %d室" % nh, 10))
        here = [st for st in g.staff if st.visible_in(b, f) and st.post is not None]
        guests = sum(1 for a in g.guests if a.state != "gone" and a.visible_in(b, f))
        bot.append(("この階の人：客%d・スタッフ%d" % (guests, len(here)), 7))
        facs = [c for c in cells if not c.is_room()]
        for c in facs[:3]:
            text = c.label
            if c.has_hygiene():
                text += "　衛生%d" % c.hygiene
                col = hyg_color(c.hygiene)
            else:
                col = 6
            if not c.is_open():
                text += "　休業中"
                col = 8
            bot.append((text, col))
        sec = g.security(b)
        bot.append(("防犯%d%%　カメラ%s" % (sec * 100, "あり" if f in b.cams else "なし"),
                    sec_color(sec)))
        self.info_box(x0, TOP_Y0 + 2, w, TOP_Y1 - TOP_Y0 - 4, title, top)
        self.info_box(x0, BOT_Y0 + 2, w, BOT_Y1 - BOT_Y0 - 4, "この階のようす", bot)

    def draw_cameras(self):
        px = self.px
        watched = self.g.monitored()
        for i in range(self.vb.cols):
            x = SX0 + SW * i + SW // 2 + 20
            y = CORR_TOP + 1
            px.rect(x - 2, y, 6, 3, 0)
            px.pset(x + 3, y + 1, 8 if watched and self.frame % 30 < 20 else 5)

    def draw_plaza(self):
        px = self.px
        x, y = SX0 + 1, BOT_Y0
        w, h = SW * 3 - 2, BOT_Y1 - BOT_Y0
        px.rect(x, y, w, h, 11)
        px.rect(x + w // 2 - 10, y, 20, h, 15)
        for i in range(12):
            fx = x + 8 + (i % 6) * 34 + (12 if i >= 6 else 0)
            fy = y + 14 + (i // 6) * 40
            px.circ(fx, fy, 3, (8, 14, 10, 7)[i % 4])
            px.pset(fx, fy, 10)
        px.circ(x + w // 2, y + h // 2, 8, 12)
        px.circb(x + w // 2, y + h // 2, 8, 7)
        self.tx_center(x + w // 2, y + h - 14, "前庭", 3)

    def label_y(self, c):
        return CORR_TOP - 13 if c.row == 0 else CORR_BOT + 2

    def draw_door(self, c, col):
        x, y, w, h = cell_rect(c)
        dy = y + h - 2 if c.row == 0 else y
        self.px.rect(c.cx - DOOR_W // 2, dy, DOOR_W, 2, col)

    def draw_lobby(self):
        px = self.px
        x, y = SX0 + 1, TOP_Y0
        w, h = SW * 2 - 2, TOP_Y1 - TOP_Y0
        px.rect(x, y, w, h, 15)
        for yy in range(y, y + h, 8):
            for xx in range(x + ((yy - y) // 8 % 2) * 8, x + w, 16):
                px.rect(xx, yy, 8, 8, 7)
        self.tx_center(x + w // 2, y + 4, "フロント", 4)
        px.rect(x + 4, y + 18, w - 8, 4, 4)
        px.rect(x + 8, CORR_TOP - 8, w - 16, 4, 4)
        px.rect(x + 8, CORR_TOP - 9, w - 16, 1, 9)
        for pxx in (x + 4, x + w - 6):
            px.circ(pxx, y + 32, 3, 3)
            px.pset(pxx, y + 32, 11)
        px.rect(x, TOP_Y1 - 1, w, 2, 6)
        lv = self.g.desk_lv
        if lv >= 2:                                          # STEP 17: check-in kiosk
            kx, ky = x + w - 26, y + 26
            px.rect(kx, ky, 10, 14, 13)
            px.rect(kx + 2, ky + 2, 6, 5, 12 if self.g.kiosk_t > 0 and self.frame % 10 < 5
                    else 6)
            px.rect(kx + 3, ky + 9, 4, 2, 0)
        if lv >= 3:                                          # concierge counter + bell
            cx0, cy0 = x + 14, y + 26
            px.rect(cx0, cy0, 22, 8, 4)
            px.rect(cx0, cy0, 22, 2, 9)
            px.circ(cx0 + 16, cy0 - 2, 2, 10)
            self.tx(cx0 - 1, cy0 + 9, "C", 10)

    # ---- facility drawers ----
    def draw_cell(self, c):
        k = c.kind
        if c.is_room():
            self.draw_room(c)
        elif c.is_food():
            self.draw_food(c)
        else:
            {"STAFFROOM": self.draw_staffroom, "MEETING": self.draw_meeting,
             "BANQUET": self.draw_banquet, "CHAPEL_HALL": self.draw_chapel,
             "SHRINE": self.draw_shrine, "YUINO": self.draw_yuino, "DRESS": self.draw_dress,
             "SECROOM": self.draw_secroom, "ONSEN": self.draw_onsen,
             "SPA": self.draw_spa, "SHOP": self.draw_shop,
             "POOL": self.draw_pool, "GYM": self.draw_gym,
             "TENANT": self.draw_tenant}[k](c)

    def draw_bed(self, bx, by, bw, sgn, col):
        px = self.px
        px.rect(bx, by, bw, 24, col)
        px.rect(bx + 1, by if sgn > 0 else by + 20, bw - 2, 4, 7)

    def draw_room(self, c):
        px = self.px
        g = self.g
        x, y, w, h = cell_rect(c)
        far_y = y + 3 if c.row == 0 else y + h - 3
        sgn = 1 if c.row == 0 else -1
        k = c.kind
        suite = k == "SUITE"
        bg = {"clean": 7, "dirty": 15, "occupied": 10, "broken": 13}[c.state]
        px.rect(x, y, w, h, bg)
        px.rectb(x, y, w, h, 2 if suite else 4)
        if g.is_ocean(c):
            wy = y if c.row == 0 else y + h - 3
            px.rect(x + 2, wy, w - 4, 3, 12)
            for i in range(x + 4, x + w - 4, 6):
                px.pset(i, wy + 1, 7)
        by = far_y if sgn > 0 else far_y - 24
        cx = c.cx + c.spec.get("bed_dx", 0)
        if k == "SINGLE":
            self.draw_bed(cx - 10, by, 12, sgn, 12)
        elif k == "DOUBLE":
            self.draw_bed(cx - 14, by, 22, sgn, 14)
        elif k == "TWIN":
            self.draw_bed(cx - 17, by, 11, sgn, 12)
            self.draw_bed(cx - 3, by, 11, sgn, 12)
        else:
            self.draw_bed(cx - 14, by, 28, sgn, 8)
        bs = 24 if suite else 18
        bath_y = far_y if sgn > 0 else far_y - bs
        px.rect(x + w - bs - 2, bath_y, bs, bs, 6)
        px.rectb(x + w - bs - 2, bath_y, bs, bs, 13)
        px.rect(x + w - bs + 1, bath_y + 4, bs // 2, bs - 8, 12)
        if suite:
            lx = x + 6
            px.rect(lx, far_y if sgn > 0 else far_y - 8, 30, 8, 2)
            px.rect(lx + 6, c.depth_y(48) - 3, 18, 7, 9)
            px.rect(lx + 44, c.depth_y(40) - 2, 4, 14, 5)
            px.circ(x + w // 2 - 4, c.depth_y(26), 3, 3)
            px.rectb(x + 1, y + 1, w - 2, h - 2, 10)
        else:
            px.rect(x + 4, c.depth_y(30) - 3, 7, 7, 4)
        if c.state == "dirty":
            for i in range(6 + 6 * suite):
                px.pset(x + 8 + i * 10, c.depth_y(20 + (i % 3) * 7), 4)
        if c.state == "broken":
            self.draw_hazard(c, "閉鎖中")
            px.circ(c.cx - 10, c.depth_y(40), 6, 12)
        num = c.number()
        self.tx(x + 3, self.label_y(c), num, 2 if suite else 1)
        tcol = {"SINGLE": 5, "DOUBLE": 8, "TWIN": 3, "SUITE": 2}[k]
        self.tx(x + 6 + text_width(num), self.label_y(c), ROOM_TAG[k], tcol)
        if c.claimed is not None and self.frame % 16 < 8:
            self.tx(x + w - 10, self.label_y(c), "*", 11)
        lv = getattr(c, "lv", 1)
        if lv >= 2:                                          # STEP 17: renovated
            rug_y = c.depth_y(44) - 4
            px.rect(c.cx - 12, rug_y, 18, 8, 14 if lv >= 3 else 6)
            px.rectb(c.cx - 12, rug_y, 18, 8, 2 if lv >= 3 else 13)
            px.circ(x + 7, c.depth_y(58), 3, 3)               # potted plant
            px.pset(x + 7, c.depth_y(58) - 3, 11)
        if lv >= 3:
            px.rectb(x + 1, y + 1, w - 2, h_rect(c) - 2, 10)  # gold frame
            for i in range(lv - 1):
                px.pset(x + w - 6 - i * 3, self.label_y(c) + 1, 10)
        h = getattr(c, "hold", None)
        if h is not None:                                    # STEP 16: reservation plate
            lab = "予約"
            tw = text_width(lab) + 4
            py = y + 2 if c.row == 1 else y + h_rect(c) - 15
            px.rect(x + w - tw - 3, py, tw, 12, HOLD_COLOR[h[0]])
            px.rectb(x + w - tw - 3, py, tw, 12, 0)
            self.tx(x + w - tw - 1, py, lab, 0)
        self.draw_door(c, bg)

    def draw_hazard(self, c, text):
        px = self.px
        x, y, w, h = cell_rect(c)
        for i in range(0, w, 8):
            px.line(x + i, y, x + i + 6, y + 6, 10)
            px.line(x + i, y + h - 7, x + i + 6, y + h - 1, 10)
        if self.frame % 30 < 20:
            tw = text_width(text)
            px.rect(c.cx - tw // 2 - 2, c.depth_y(30) - 7, tw + 4, 13, 0)
            self.tx_center(c.cx, c.depth_y(30) - 6, text, 8)

    def draw_hyg_bar(self, c):
        px = self.px
        x, y, w, h = cell_rect(c)
        bx0, by0 = x + w - 22, self.label_y(c) + 4
        px.rect(bx0, by0, 18, 3, 0)
        px.rect(bx0, by0, max(1, int(18 * c.hygiene / 100)), 3, hyg_color(c.hygiene))

    def draw_dirt(self, c):
        px = self.px
        x, y, w, h = cell_rect(c)
        hy = c.hygiene
        if hy < HYGIENE_WARN:
            for i in range(int((HYGIENE_WARN - hy) / 4)):
                px.pset(x + 5 + (i * 23) % (w - 10), c.depth_y(20 + (i * 11) % 36), 4)
            for i in range(1 if hy >= HYGIENE_DANGER else 3):
                fx = c.cx + int(10 * math.sin((self.frame + i * 40) / 6.0)) - 10 + i * 10
                fy = c.depth_y(34 + int(6 * math.cos((self.frame + i * 25) / 5.0)))
                px.pset(fx, fy, 0)
                px.pset(fx + 1, fy - 1, 13)

    def draw_food(self, c):
        px = self.px
        g = self.g
        x, y, w, h = cell_rect(c)
        far_y = y + 3 if c.row == 0 else y + h - 3
        sgn = 1 if c.row == 0 else -1
        k = c.kind
        floor_col = {"CAFE": 15, "WASHOKU": 9, "BUFFET": 14, "BAR": 1, "CHINESE": 2,
                     "ITALIAN": 15, "FRENCH": 7}[k]
        px.rect(x, y, w, h, floor_col)
        px.rectb(x, y, w, h, c.spec["color"])
        ky = far_y if sgn > 0 else far_y - 12
        px.rect(x + 3, ky, w - 6, 12, 5 if k == "BAR" else 6)
        for i in range((w - 10) // 12):
            px.rect(x + 6 + i * 12, ky + 3, 8, 6, 13 if k != "BAR" else 2)
        tables = []
        if k == "CAFE":
            tables = [(dx, d) for dx in (-16, 16) for d in (32, 50)]
            for dx, d in tables:
                px.circ(c.cx + dx, c.depth_y(d), 3, 4)
        elif k == "WASHOKU":
            px.rect(x + 2, y + 2, w - 4, h - 4, 9)
            for i in range(x + 4, x + w - 4, 18):
                px.line(i, y + 4, i, y + h - 5, 10)
            px.rect(x + 3, ky, w - 6, 12, 4)
            tables = [(dx, d) for dx in (-48, -16, 16, 48) for d in (32, 52)]
            for dx, d in tables:
                px.rect(c.cx + dx - 5, c.depth_y(d) - 3, 10, 6, 4)
        elif k == "BUFFET":
            px.rect(c.cx - 44, c.depth_y(58) - 3, 88, 6, 7)
            for i in range(9):
                px.circ(c.cx - 40 + i * 10, c.depth_y(58), 2, [8, 10, 11, 9][i % 4])
            tables = [(dx, d) for dx in (-52, -26, 0, 26, 52) for d in (28, 42)]
            for dx, d in tables:
                px.circ(c.cx + dx, c.depth_y(d), 3, 4)
        elif k == "BAR":
            px.rect(x + 6, c.depth_y(62) - 2, w - 12, 4, 4)
            tables = [(dx, 52) for dx in (-21, -7, 7, 21)] + [(-14, 32), (14, 32)]
            for dx, d in tables:
                px.circ(c.cx + dx, c.depth_y(d), 2, 2)
        elif k == "CHINESE":                                 # STEP 18: round tables
            px.rect(x + 3, ky, w - 6, 12, 8)
            for i in range(x + 8, x + w - 8, 16):            # lanterns
                px.circ(i, ky + 6, 2, 8 if (i // 16 + self.frame // 20) % 2 else 9)
            tables = [(dx, d) for dx in (-40, 0, 40) for d in (30, 54)]
            for dx, d in tables:
                px.circ(c.cx + dx, c.depth_y(d), 6, 8)
                px.circb(c.cx + dx, c.depth_y(d), 6, 10)
                px.circ(c.cx + dx, c.depth_y(d), 2, 7)       # lazy susan
        elif k == "ITALIAN":
            for yy in range(y + 2, y + h - 2, 6):            # checked floor
                for xx in range(x + 2 + ((yy - y) // 6 % 2) * 6, x + w - 2, 12):
                    px.rect(xx, yy, 6, 6, 14)
            px.rect(x + 3, ky, w - 6, 12, 4)
            px.circ(x + w - 10, ky + 6, 4, 9)                # pizza oven
            px.circ(x + w - 10, ky + 6, 2, 8 if self.frame % 20 < 10 else 10)
            tables = [(dx, d) for dx in (-14, 14) for d in (30, 50)]
            for dx, d in tables:
                px.rect(c.cx + dx - 5, c.depth_y(d) - 4, 10, 8, 7)
                px.rectb(c.cx + dx - 5, c.depth_y(d) - 4, 10, 8, 8)
        elif k == "FRENCH":
            px.rect(x + 2, y + 2, w - 4, h - 4, 1)           # dark carpet
            px.rect(x + 3, ky, w - 6, 12, 13)
            px.circ(c.cx, c.depth_y(44), 5, 10)              # chandelier glow
            px.circ(c.cx, c.depth_y(44), 2, 7)
            tables = [(dx, d) for dx in (-46, -18, 18, 46) for d in (30, 58)]
            for dx, d in tables:
                px.rect(c.cx + dx - 6, c.depth_y(d) - 4, 12, 8, 7)
                px.pset(c.cx + dx, c.depth_y(d), 8)          # candle
        s = c.spec["serve"]
        lunch_now = getattr(c, "lunch", False) and LUNCH_T - 20 <= g.t <= LUNCH_T + 150
        if (s - 20 <= g.t <= s + 150 or lunch_now) and c.served_today and tables:
            for i in range(min(len(tables) * 2, c.served_today)):
                dx, d = tables[i // 2]
                px.circ(c.cx + dx + (-5 if i % 2 == 0 else 5), c.depth_y(d), 1, 12)
        self.draw_dirt(c)
        self.tx(x + 3, self.label_y(c), c.label, 7 if k in ("BAR", "FRENCH", "CHINESE") else 1)
        if getattr(c, "lunch", False):
            self.tx(x + 3 + text_width(c.label) + 3, self.label_y(c), "昼", 9)
        self.draw_hyg_bar(c)
        if not c.is_open():
            self.draw_hazard(c, "休業中")
        self.draw_door(c, floor_col)

    def draw_staffroom(self, c):
        px = self.px
        x, y, w, h = cell_rect(c)
        far_y = y + 3 if c.row == 0 else y + h - 3
        px.rect(x, y, w, h, 3)
        px.rectb(x, y, w, h, 1)
        px.rect(c.cx - 14, c.depth_y(64) - 3, 28, 7, 4)
        px.rect(c.cx - 6, c.depth_y(40) - 4, 12, 8, 9)
        px.rect(x + 4, far_y if c.row == 0 else far_y - 8, 8, 8, 12)
        self.tx(x + 3, self.label_y(c), "休憩室", 7)
        self.tx(x + w - 22, self.label_y(c), "%d/%d" % (len(c.seats), c.spec["seats"]), 7)
        if c.seats and self.frame % 40 < 30:
            self.tx(c.cx + 12, c.depth_y(52) - 6, "zZ", 7)
        self.draw_door(c, 3)

    def draw_secroom(self, c):
        px = self.px
        g = self.g
        x, y, w, h = cell_rect(c)
        far_y = y + 3 if c.row == 0 else y + h - 3
        px.rect(x, y, w, h, 1)
        px.rectb(x, y, w, h, 5)
        my = far_y if c.row == 0 else far_y - 14
        watching = bool(g.guards_on(("FAC", c)))
        for i in range(6):
            mx = x + 5 + (i % 3) * 21
            yy = my + (i // 3) * 7
            px.rect(mx, yy, 18, 6, 0)
            if watching:
                col = (3, 12, 6, 11)[(i + self.frame // 15) % 4]
                px.rect(mx + 1, yy + 1, 16, 4, col)
        px.rect(c.cx - 16, c.depth_y(46) - 3, 32, 6, 4)
        self.tx(x + 3, self.label_y(c), "警備室", 6)
        if watching and self.frame % 40 < 30:
            self.tx(x + w - 26, self.label_y(c), "監視", 11)
        self.draw_door(c, 1)

    def draw_onsen(self, c):
        px = self.px
        g = self.g
        x, y, w, h = cell_rect(c)
        outdoor = rs.open_air(c)
        px.rect(x, y, w, h, 3 if outdoor else 13)
        px.rectb(x, y, w, h, 4)
        if outdoor:
            for i in range(0, w, 14):
                px.circ(x + 4 + i, y + 4, 3, 11)
                px.circ(x + 4 + i, y + h - 5, 3, 11)
        py0, py1 = sorted((c.depth_y(22), c.depth_y(70)))
        px.rect(x + 10, py0, w - 20, py1 - py0, 12)
        for i in range(x + 10, x + w - 10, 9):
            px.circ(i, py0, 3, 13)
            px.circ(i + 4, py1, 3, 13)
        px.circ(x + 10, (py0 + py1) // 2, 4, 13)
        px.circ(x + w - 10, (py0 + py1) // 2, 4, 13)
        bathing = BATH_T - 30 <= g.t <= BATH_T + 220
        if bathing:
            for i in range(min(16, c.served_today)):
                px.circ(x + 18 + (i % 8) * 15, py0 + 8 + (i // 8) * 18, 2, 15)
        if bathing or g.season() == "WINTER":
            for i in range(6):
                sx = x + 16 + i * 22 + int(3 * math.sin((self.frame + i * 13) / 8.0))
                sy = (self.frame // 3 + i * 7) % max(1, py1 - py0 - 10)
                px.pset(sx, py1 - sy - 6, 7)
                px.pset(sx + 1, py1 - sy - 7, 7)
        self.draw_dirt(c)
        if rs.sauna(c):                                       # STEP 17: sauna hut
            sx = x + w - 26
            sy = c.depth_y(70) if c.row == 0 else c.depth_y(70) - 14
            px.rect(sx, sy, 20, 14, 4)
            px.rectb(sx, sy, 20, 14, 2)
            for i in range(3):
                px.line(sx + 3, sy + 3 + i * 4, sx + 16, sy + 3 + i * 4, 9)
            if self.frame % 30 < 20:
                px.pset(sx + 10, sy - 2, 7)
        self.tx(x + 3, self.label_y(c), "露天風呂" if outdoor else "大浴場", 1)
        self.draw_hyg_bar(c)
        if not c.is_open():
            self.draw_hazard(c, "休業中")
        self.draw_door(c, 13)

    def draw_spa(self, c):
        px = self.px
        g = self.g
        x, y, w, h = cell_rect(c)
        px.rect(x, y, w, h, 15)
        px.rectb(x, y, w, h, 14)
        t0, t1 = sorted((c.depth_y(26), c.depth_y(62)))
        for i in range(3):
            bx = x + 6 + i * 21
            px.rect(bx, t0, 14, t1 - t0, 7)
            px.rect(bx + 2, t0 + (0 if c.row == 1 else t1 - t0 - 6), 10, 6, 14)
            if BATH_T - 30 <= g.t <= BATH_T + 220 and i < c.served_today:
                px.circ(bx + 7, (t0 + t1) // 2, 3, 12)
        px.circ(x + w - 6, c.depth_y(70), 3, 3)
        self.draw_dirt(c)
        self.tx(x + 3, self.label_y(c), "スパ", 2)
        self.draw_hyg_bar(c)
        if not c.is_open():
            self.draw_hazard(c, "休業中")
        self.draw_door(c, 15)

    def draw_pool(self, c):
        px = self.px
        g = self.g
        x, y, w, h = cell_rect(c)
        open_ = ls.pool_open(g, c)
        in_ = ls.indoor(c)
        night = ls.night_pool(c) and g.t >= NIGHT_POOL_T - 120
        px.rect(x, y, w, h, 13 if in_ else 15)                # tiles / deck
        for i in range(x + 2, x + w - 2, 8):
            px.line(i, y + 2, i, y + h - 3, 6 if in_ else 9)
        p0, p1 = sorted((c.depth_y(16), c.depth_y(68)))
        water = (12 if open_ else 6) if not night else 2
        px.rect(x + 10, p0, w - 20, p1 - p0, water)
        px.rectb(x + 10, p0, w - 20, p1 - p0, 7)
        if open_:
            for i in range(4):                               # ripples + lanes
                yy = p0 + 6 + i * ((p1 - p0 - 8) // 4)
                ox = (self.frame // 6 + i * 5) % 12
                for xx in range(x + 14 + ox, x + w - 14, 12):
                    px.line(xx, yy, xx + 4, yy, 6 if not night else 14)
        else:
            px.rect(x + 12, p0 + 2, w - 24, p1 - p0 - 4, 13)  # cover sheet
        for i in range(3):                                   # deck chairs + umbrellas
            dx = x + 18 + i * (w - 36) // 2
            dy = p1 + 6 if c.row == 0 else p0 - 10
            dy = max(y + 2, min(y + h - 8, dy))
            px.rect(dx - 4, dy, 8, 4, 7)
            if not in_:
                px.circ(dx, dy - 3, 4, (8, 10, 14)[i])
        if night and open_:                                  # night pool lights
            for i in range(x + 12, x + w - 12, 14):
                px.pset(i, p0 - 1, (14, 10, 12, 8)[(i // 14 + self.frame // 10) % 4])
        if in_:
            px.rectb(x + 1, y + 1, w - 2, h - 2, 6)           # glass roof frame
        lab = "ナイトプール" if night and open_ else ("屋内プール" if in_ else "プール")
        self.tx(x + 3, self.label_y(c), lab, 1 if not night else 14)
        if c.served_today:
            self.tx(x + w - 40, self.label_y(c), "%d人" % c.served_today, 5)
        self.draw_hyg_bar(c)
        if not c.is_open():
            self.draw_hazard(c, "閉鎖中")
        self.draw_door(c, 15)

    def draw_gym(self, c):
        px = self.px
        g = self.g
        x, y, w, h = cell_rect(c)
        px.rect(x, y, w, h, 5)
        px.rectb(x, y, w, h, 1)
        for i in range(3):                                   # treadmills
            tx = x + 6 + i * 20
            ty = c.depth_y(58) - 6
            px.rect(tx, ty, 14, 12, 0)
            px.rect(tx + 2, ty + 2, 10, 8, 13 if (self.frame // 4 + i) % 2 else 1)
        bx, by = c.cx - 12, c.depth_y(30)                   # barbell rack
        px.line(bx, by, bx + 24, by, 13)
        px.rect(bx - 2, by - 3, 3, 7, 0)
        px.rect(bx + 23, by - 3, 3, 7, 0)
        if c.lv >= 3:                                        # studio mirror
            px.rect(x + w - 8, y + 4, 4, h - 8, 6)
        n = min(6, int(g.gym_members) // 6)
        for i in range(n):                                   # members working out
            mx = x + 8 + (i * 11) % (w - 16)
            my = c.depth_y(44 + (i % 2) * 8)
            jump = 1 if (self.frame // 6 + i) % 2 else 0
            art.person(px, mx, my - jump, (8, 11, 12, 14, 9, 10)[i], hair=art.hair_of(i))
        self.tx(x + 3, self.label_y(c), "ジム", 7)
        self.tx(x + w - 30, self.label_y(c), "%d人" % int(g.gym_members), 10)
        self.draw_hyg_bar(c)
        self.draw_door(c, 5)

    def draw_shop(self, c):
        px = self.px
        x, y, w, h = cell_rect(c)
        far_y = y + 3 if c.row == 0 else y + h - 3
        px.rect(x, y, w, h, 15)
        px.rectb(x, y, w, h, 9)
        sy = far_y if c.row == 0 else far_y - 10
        for row in range(2):                                 # shelves with goods
            yy = sy + row * 12 * (1 if c.row == 0 else -1)
            px.rect(x + 4, yy, w - 8, 8, 4)
            for i in range(x + 6, x + w - 8, 5):
                px.rect(i, yy + 2, 3, 4, (8, 10, 11, 12, 14)[(i // 5 + row) % 5])
        cy = c.depth_y(20)
        px.rect(c.cx - 14, cy - 3, 28, 6, 9)                 # counter + register
        px.rect(c.cx + 6, cy - 5, 5, 3, 0)
        if self.g.weather_at() in ("RAIN", "SNOW"):           # umbrella stand
            ux = x + w - 10
            px.rect(ux, c.depth_y(34) - 4, 6, 9, 13)
            for i, col in enumerate((8, 12, 10)):
                px.line(ux + 1 + i * 2, c.depth_y(34) - 8, ux + 1 + i * 2, c.depth_y(34) - 4, col)
        self.tx(x + 3, self.label_y(c), "売店", 4)
        if c.served_today:
            self.tx(x + w - 26, self.label_y(c), "%d" % c.served_today, 9)
        self.draw_door(c, 15)

    def draw_tenant(self, c):
        px = self.px
        x, y, w, h = cell_rect(c)
        far_y = y + 3 if c.row == 0 else y + h - 3
        br = sh.brand_of(c)
        if br is None:
            px.rect(x, y, w, h, 13)
            px.rectb(x, y, w, h, 5)
            for i in range(0, w, 10):
                px.line(x + i, y + 2, x + i + 6, y + 8, 5)
            self.tx_center(c.cx, c.depth_y(40) - 6, "テナント募集", 1)
            self.tx(x + 3, self.label_y(c), "空き区画", 5)
            self.draw_door(c, 13)
            return
        col = br["color"]
        px.rect(x, y, w, h, 7)
        px.rect(x + 2, y + 2, w - 4, h - 4, 15 if col != 10 else 1)
        px.rectb(x, y, w, h, col)
        sy = far_y if c.row == 0 else far_y - 12
        px.rect(x + 4, sy, w - 8, 12, col)                   # brand wall
        self.tx_center(c.cx, sy + 1, br["short"], 7 if col != 10 else 0)
        for i in range(3):                                   # display cases
            dx = c.cx - 40 + i * 40
            dy = c.depth_y(44)
            px.rect(dx - 8, dy - 5, 16, 10, 6)
            px.rectb(dx - 8, dy - 5, 16, 10, 7)
            if self.frame % 40 < 30:
                px.pset(dx - 3 + i, dy - 1, 10 if col == 10 else col)
        for i in (-1, 1):                                    # mannequins
            mx = c.cx + i * 58
            if x + 4 < mx < x + w - 4:
                art.person(px, mx, c.depth_y(26), col, hair=0, skin=13, legs=13)
        self.tx(x + 3, self.label_y(c), br["label"][:8], 7 if col != 10 else 10)
        self.draw_door(c, 7)

    def draw_meeting(self, c):
        px = self.px
        x, y, w, h = cell_rect(c)
        far_y = y + 3 if c.row == 0 else y + h - 3
        px.rect(x, y, w, h, 6)
        px.rectb(x, y, w, h, 5)
        px.rect(x + 10, far_y if c.row == 0 else far_y - 4, w - 20, 4, 7)
        t0, t1 = sorted((c.depth_y(22), c.depth_y(66)))
        px.rect(c.cx - 5, t0, 10, t1 - t0, 4)
        for i in range(10):
            sx, sy = bk.seat_pt(c, i)
            px.rect(sx + (-2 if sx < c.cx else 0), sy - 1, 3, 3, 13)
        busy = c.rented or any(c in b.rooms_used for b in bk.today_bookings(self.g))
        self.tx(x + 3, self.label_y(c), "会議室", 1)
        if busy:
            self.tx(x + w - 26, self.label_y(c), "使用", 8)
        self.draw_door(c, 6)

    def draw_banquet(self, c):
        px = self.px
        g = self.g
        x, y, w, h = cell_rect(c)
        far_y = y + 3 if c.row == 0 else y + h - 3
        sgn = 1 if c.row == 0 else -1
        wedding = any(b.kind == "WEDDING" and c in b.cells_used for b in bk.today_bookings(g))
        px.rect(x, y, w, h, 2)
        px.rect(x + 3, y + 3, w - 6, h - 6, 15 if wedding else 14)
        sy = far_y if sgn > 0 else far_y - 12
        px.rect(c.cx - 30, sy, 60, 12, 7 if wedding else 10)
        px.rect(c.cx - 26, sy + (2 if sgn > 0 else 6), 52, 4, 14 if wedding else 9)
        px.rect(x + 4, sy, 16, 12, 6)
        served = any(b.banquet and (b.served or 0) > 0 for b in bk.today_bookings(g))
        for t in range(6):
            tx = c.cx + (-46, 0, 46)[t % 3]
            ty = c.depth_y((30, 56)[t // 3])
            px.circ(tx, ty, 4, 7)
            px.circb(tx, ty, 4, 14 if wedding else 13)
            if served:
                px.pset(tx, ty, 8)
        self.draw_dirt(c)
        self.tx(x + 3, self.label_y(c), "宴会場", 7)
        if wedding:
            self.tx(x + 44, self.label_y(c), "披露宴", 8)
        self.draw_hyg_bar(c)
        if not c.is_open():
            self.draw_hazard(c, "休業中")
        self.draw_door(c, 14)

    def draw_chapel(self, c):
        px = self.px
        x, y, w, h = cell_rect(c)
        far_y = y + 3
        px.rect(x, y, w, h, 7)
        px.rectb(x, y, w, h, 13)
        for i in range(5):
            gx = c.cx - 40 + i * 20
            px.rect(gx - 4, far_y, 8, 6, (12, 8, 10, 11, 14)[i])
        px.rect(c.cx - 14, c.depth_y(70) - 2, 28, 6, 15)
        px.line(c.cx, c.depth_y(76), c.cx, c.depth_y(68), 10)
        px.line(c.cx - 3, c.depth_y(73), c.cx + 3, c.depth_y(73), 10)
        px.rect(c.cx - 6, c.depth_y(60), 12, 60, 8)
        for row in range(4):
            yy = c.depth_y(22 + row * 10)
            for side in (-1, 1):
                x0 = c.cx + 18 if side > 0 else c.cx - 18 - 50
                px.rect(x0, yy + 2, 50, 3, 4)
        self.tx(x + 3, self.label_y(c), "礼拝堂", 1)
        if any(b.kind == "WEDDING" and c in b.cells_used for b in bk.today_bookings(self.g)):
            self.tx(x + w - 50, self.label_y(c), "本日挙式", 8)
        self.draw_door(c, 7)

    def draw_shrine(self, c):
        px = self.px
        x, y, w, h = cell_rect(c)
        far_y = y + 3 if c.row == 0 else y + h - 3
        sgn = 1 if c.row == 0 else -1
        px.rect(x, y, w, h, 9)
        px.rectb(x, y, w, h, 4)
        for i in range(x + 4, x + w - 4, 18):
            px.line(i, y + 4, i, y + h - 5, 10)
        ay = far_y if sgn > 0 else far_y - 14
        px.rect(c.cx - 30, ay, 60, 14, 7)
        px.rect(c.cx - 26, ay + (10 if sgn > 0 else 0), 52, 4, 4)
        px.circ(c.cx - 20, ay + 6, 3, 8)
        px.circ(c.cx + 20, ay + 6, 3, 8)
        px.rect(c.cx - 2, ay + 2, 4, 8, 10)
        for i in range(x + 6, x + w - 6, 10):
            px.pset(i, ay + (16 if sgn > 0 else -3), 10)
        self.tx(x + 3, self.label_y(c), "神殿", 1)
        if any(b.kind == "WEDDING" and c in b.cells_used for b in bk.today_bookings(self.g)):
            self.tx(x + 30, self.label_y(c), "本日挙式", 8)
        self.draw_door(c, 9)

    def draw_yuino(self, c):
        px = self.px
        x, y, w, h = cell_rect(c)
        far_y = y + 3 if c.row == 0 else y + h - 3
        px.rect(x, y, w, h, 9)
        px.rectb(x, y, w, h, 4)
        for i in range(x + 4, x + w - 4, 16):
            px.line(i, y + 4, i, y + h - 5, 10)
        t0, t1 = sorted((c.depth_y(24), c.depth_y(58)))
        px.rect(c.cx - 7, t0, 14, t1 - t0, 4)
        px.rect(x + 4, far_y if c.row == 0 else far_y - 10, 14, 10, 7)
        px.pset(x + 10, (far_y if c.row == 0 else far_y - 10) + 4, 8)
        self.tx(x + 3, self.label_y(c), "結納の間", 1)
        self.draw_door(c, 9)

    def draw_dress(self, c):
        px = self.px
        x, y, w, h = cell_rect(c)
        far_y = y + 3 if c.row == 0 else y + h - 3
        px.rect(x, y, w, h, 14)
        px.rectb(x, y, w, h, 2)
        ry = far_y if c.row == 0 else far_y - 4
        px.rect(x + 6, ry, w - 12, 2, 13)
        for i in range(5):
            dx = x + 10 + i * 12
            px.rect(dx - 3, ry + 2, 7, 12, (7, 7, 15, 7, 14)[i])
        px.rect(x + w - 14, c.depth_y(40) - 10, 8, 20, 6)
        px.rect(c.cx - 8, c.depth_y(52) - 2, 6, 4, 4)
        self.tx(x + 3, self.label_y(c), "衣装室", 2)
        self.draw_door(c, 14)

    # ---- people (STEP 12: pixel-art sprites) ----
    def anim(self, a):
        """(step, face) from the agent's movement since the last frame"""
        m = self.motion.get(a)
        if m is None:
            m = [a.x, a.y, 1, -99]
            self.motion[a] = m
        dx = a.x - m[0]
        if dx or a.y != m[1]:
            m[3] = self.frame
            if dx:
                m[2] = 1 if dx > 0 else -1
            m[0], m[1] = a.x, a.y
        moving = self.frame - m[3] < 6
        step = 1 + (self.frame // 5) % 2 if moving else 0
        return step, m[2]

    def draw_mark(self, x, y, mark, mcol):
        if mark:
            self.tx(int(x) - text_width(mark) // 2, int(y) - 18, mark, mcol)

    def guest_look(self, a):
        g = self.g
        blink = self.frame % 20 < 12
        mark, mcol = None, 8
        if a.sick:
            mark, mcol = "@", 3
        elif a.robbed and blink:
            mark, mcol = "!?", 9
        elif a.angry and blink:
            mark = "!!"
        elif a.state == "queue_desk" and a.desk_wait > g.patience(a) * 0.6 and blink:
            mark = "!"
        body = 3 if a.sick else (8 if a.angry else a.spec["color"])
        return body, mark, mcol

    def draw_guest(self, a, step, face):
        px = self.px
        key = id(a) // 16
        body, mark, mcol = self.guest_look(a)
        skin = 11 if a.sick else (14 if a.angry else 15)
        if a.gtype == "BUSINESS":
            look = dict(body=3 if a.sick else 13, accent=8, legs=5, shoes=0)
        else:
            look = dict(body=3 if a.sick else art.shirt_of(key), legs=4, shoes=4)
        if a.party == 2 and a.state != "checkin":
            art.person(px, a.x + 5 * face * -1, a.y + 1, art.shirt_of(key + 3),
                       hair=art.hair_of(key + 5), skin=skin, step=step, face=face,
                       dress=(key % 2 == 0), legs=4)
        art.person(px, a.x, a.y, hair=art.hair_of(key), skin=skin, step=step, face=face,
                   glasses=a.celeb, **look)
        if a.vip and self.frame % 30 < 20:
            px.pset(int(a.x), int(a.y) - 7, 10)
        if a.celeb:
            mark, mcol = mark or "★", 10 if mark is None or mark == "★" else mcol
        self.draw_mark(a.x, a.y, mark, mcol)

    def draw_agents(self):
        g = self.g
        px = self.px
        b, f = self.vb, self.vf
        blink = self.frame % 20 < 12
        sleeping = art.late(g.t)
        for a in g.guests:
            if a.state == "gone" or not a.visible_in(b, f):
                continue
            if sleeping and a.state == "in_room":
                continue                    # asleep in a dark room
            step, face = self.anim(a)
            self.draw_guest(a, step, face)
        for v in g.visitors:
            if v.state == "gone" or not v.visible_in(b, f):
                continue
            step, face = self.anim(v)
            key = id(v) // 16
            if v.wrole == "BRIDE":
                art.person(px, v.x, v.y, 7, hair=7, step=step, face=face, dress=True, hat=7)
                if self.frame % 20 < 10:
                    px.pset(int(v.x) + 2, int(v.y) - 1, 14)       # bouquet
            elif v.wrole == "GROOM":
                art.person(px, v.x, v.y, 0, hair=art.hair_of(key), accent=7, legs=0,
                           step=step, face=face)
            elif v.color == LEISURE_COLOR and v.cell is not None and \
                    v.cell.kind == "POOL" and v.state == "stay":       # STEP 20: swimmer
                bob = 1 if (self.frame // 8 + key) % 2 else 0
                px.pset(int(v.x), int(v.y) - 1 + bob, art.hair_of(key))
                px.pset(int(v.x), int(v.y) + bob, 15)
                px.pset(int(v.x) - 1, int(v.y) + 1 + bob, 15)
                px.pset(int(v.x) + 1, int(v.y) + 1 + bob, 15)
                px.circb(int(v.x), int(v.y) + 1, 3, 7)
            elif v.color == SHOPPER_COLOR:                         # STEP 19: shopper
                art.person(px, v.x, v.y, 13, hair=art.hair_of(key), legs=1, step=step,
                           face=face, dress=(key % 2 == 0), accent=art.shirt_of(key))
                if v.state == "leave" and key % 2:
                    px.rect(int(v.x) + 3 * face, int(v.y) - 1, 3, 3, art.shirt_of(key + 1))
            elif v.color == OUTSIDE_COLOR:                         # STEP 18: outside diner
                art.person(px, v.x, v.y, art.shirt_of(key + 2), hair=art.hair_of(key),
                           legs=5, step=step, face=face, dress=(key % 3 == 0))
            elif v.color == 14:                                    # party guest
                art.person(px, v.x, v.y, art.shirt_of(key), hair=art.hair_of(key),
                           dress=(key % 2 == 0), legs=4, step=step, face=face)
            else:                                                  # business visitor
                art.person(px, v.x, v.y, v.color, hair=art.hair_of(key), accent=7,
                           legs=5, step=step, face=face)
        for st in g.staff:
            if st.post is None or not st.visible_in(b, f):
                continue
            step, face = self.anim(st)
            mark = None
            if st.state == "work" and self.frame % 16 < 8:
                mark = "*"
            elif st.fatigue >= 80 and blink and st.state != "rest":
                mark = "~"
            hair = art.hair_of(st.id)
            if st.role == "FRONT":
                art.person(px, st.x, st.y, 1, hair=hair, accent=7, legs=1, step=step,
                           face=face)
            elif st.role == "CLEANER":
                art.person(px, st.x, st.y, 11, hair=hair, hat=3, apron=7, legs=5,
                           step=step, face=face)
            elif st.role == "COOK":
                art.person(px, st.x, st.y, 7, hair=hair, hat=7, accent=8, legs=13,
                           step=step, face=face)
                px.pset(int(st.x), int(st.y) - 6, 7)                  # tall toque
            elif st.role == "GUARD":
                art.person(px, st.x, st.y, 5, hair=hair, hat=1, accent=10, legs=1,
                           step=step, face=face)
                if g.t >= art.NIGHT_START or g.t < art.DAWN_END:  # flashlight beam
                    art.glow(px, int(st.x) + 6 * face, int(st.y), 3, 10)
            if st.state == "rest" and self.frame % 40 < 30:
                mark = mark or "z"
            self.draw_mark(st.x, st.y, mark, 8 if mark in ("~",) else 10)

    def draw_cursor(self):
        px = self.px
        col = 10 if self.frame % 20 < 14 else 9
        if self.preview is not None:
            a, n = self.preview
            x, y, w, h = slot_rect(a, self.vb.cols)
            w += SW * (n - 1)
            if self.frame % 10 < 7:
                px.rectb(x - 1, y - 1, w + 2, h + 2, 11)
                px.rectb(x, y, w, h, 11)
            return
        if self.menus or self.vf > self.g.max_floor(self.vb) or self.vb.fixed():
            return
        self.cx = clamp(self.cx, 0, self.vb.cols - 1)
        s = self.cy * self.vb.cols + self.cx
        c = self.vb.grid[self.vf][s]
        x, y, w, h = slot_rect(s, self.vb.cols)
        if self.vb.is_main() and self.vf == 0 and s in LOBBY_RESERVED:
            x, w = SX0 + 1, SW * 2 - 2
        elif c is not None:
            x, y, w, h = cell_rect(c)
        px.rectb(x - 1, y - 1, w + 2, h + 2, col)
        px.rectb(x, y, w, h, col)

    # ---- site map ----
    def lot_door(self, lot):
        x, y, w, h = lot_rect(lot)
        return (x + w // 2, y + h + LOT_GAP // 2)

    def route(self, fr, to):
        (ax, ay), (bx, by) = self.lot_door(fr), self.lot_door(to)
        if ay == by:
            return [(ax, ay), (bx, by)]
        col = fr[0]
        if to[0] > col:
            gx = LOT_X0 + (col + 1) * (LOT_W + LOT_GAP) - LOT_GAP // 2
        else:
            gx = LOT_X0 + col * (LOT_W + LOT_GAP) - LOT_GAP // 2
        return [(ax, ay), (gx, ay), (gx, by), (bx, by)]

    @staticmethod
    def along(pts, p):
        segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        total = sum(abs(b[0] - a[0]) + abs(b[1] - a[1]) for a, b in segs) or 1
        d = p * total
        for a, b in segs:
            L = abs(b[0] - a[0]) + abs(b[1] - a[1])
            if d <= L or (a, b) == segs[-1]:
                r = 0 if L == 0 else min(1.0, d / L)
                return a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r
            d -= L
        return pts[-1]

    def draw_site(self):
        px = self.px
        g = self.g
        x0 = PANEL_W
        ph = art.phase(g.t)
        art.set_tint(px, art.OUT_TINT[ph])
        try:
            px.rect(x0, MY, W - x0, MB - MY, 13)
            for lx in range(SITE_COLS):
                for ly in range(SITE_ROWS):
                    self.draw_lot((lx, ly))
            for b in g.buildings:
                if b.walkway and not b.is_main():
                    pts = self.route(b.lot, g.main.lot)
                    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
                        px.rect(min(ax, bx) - 1, min(ay, by) - 1, abs(bx - ax) + 3,
                                abs(by - ay) + 3, 9)
        finally:
            art.reset_tint(px)
        if ph in ("DUSK", "NIGHT"):
            self.draw_site_lights(ph)
        if not self.menus:
            x, y, w, h = lot_rect(self.lot)
            col = 10 if self.frame % 20 < 14 else 9
            px.rectb(x - 2, y - 2, w + 4, h + 4, col)
            px.rectb(x - 1, y - 1, w + 2, h + 2, col)
        for a in g.outdoor_walkers():
            fr, to, total = a.trip
            p = 1.0 - a.transit / max(1, total)
            x, y = self.along(self.route(fr, to), p)
            if isinstance(a, Guest):
                col = 13 if a.gtype == "BUSINESS" else art.shirt_of(id(a) // 16)
            elif isinstance(a, Staff):
                col = ROLES[a.role]["color"]
            else:
                col = 7 if getattr(a, "wrole", None) == "BRIDE" else a.color
            art.tiny(px, x, y, col, art.hair_of(id(a) // 16), (self.frame // 5) % 2)
            if g.weather_at() == "RAIN" and not g.covered(fr, to):      # umbrella
                px.line(int(x) - 2, int(y) - 3, int(x) + 2, int(y) - 3, 8)
        self.draw_weather_fx()

    def draw_site_lights(self, ph):
        """street lamps + lit windows at dusk / night"""
        px = self.px
        g = self.g
        for i in range(1, SITE_COLS):
            for j in range(0, SITE_ROWS + 1):
                x = LOT_X0 + i * (LOT_W + LOT_GAP) - LOT_GAP // 2 - 1
                y = LOT_Y0 + j * (LOT_H + LOT_GAP) - LOT_GAP // 2 - 1
                if y < MY or y > MB:
                    continue
                art.glow(px, x, y, 5, 9 if ph == "NIGHT" else 10)
                px.pset(x, y, 10)
        for b in g.buildings:
            x, y, w, h = lot_rect(b.lot)
            top = y + (7 if g.trait(b.lot) == "STATION" else 3)
            if b.kind == "CHAPEL":
                if ph == "NIGHT":
                    for i in range(3):
                        px.pset(x + 18 + i * 12, top + 14, (14, 10, 12)[i])
                continue
            for f in range(min(b.floors, 7)):
                if f > g.max_floor(b):
                    continue
                occ = any(c.state == "occupied" for c in g.floor_cells(b, f) if c.is_room())
                if occ or b.is_main() and f == 0:
                    px.rect(x + 8 + f * 7, top + 15, 4, 4, 10)
                    if (f + self.frame // 40) % 5 == 0:
                        px.pset(x + 9 + f * 7, top + 16, 9)      # someone moves
            dx, _ = self.lot_door(b.lot)
            art.glow(px, dx, top + 38, 3, 10)                  # entrance light

    def draw_weather_fx(self):
        px = self.px
        w = self.g.weather_at()
        if w not in ("RAIN", "SNOW"):
            return
        x0, x1, y0, y1 = PANEL_W, W, MY, MB
        for i in range(70):
            x = x0 + (i * 53 + self.frame * (3 if w == "RAIN" else 1)) % (x1 - x0)
            y = y0 + (i * 37 + self.frame * (6 if w == "RAIN" else 1)) % (y1 - y0)
            if w == "RAIN":
                px.line(x, y, x - 1, y + 3, 6)
            else:
                px.pset(x, y, 7)

    def draw_lot_base(self, lot, owned):
        px = self.px
        x, y, w, h = lot_rect(lot)
        t = self.g.trait(lot)
        px.rect(x, y, w, h, 11 if owned else 3)
        if t == "OCEAN":
            px.rect(x, y + h - 12, w, 12, 12)
            px.rect(x, y + h - 15, w, 3, 15)
            for i in range(x + 3, x + w - 3, 8):
                ox = (self.frame // 10) % 4
                px.line(i + ox, y + h - 7, i + ox + 3, y + h - 7, 7)
        elif t == "STATION":
            px.rect(x, y, w, 6, 13)
            px.line(x, y + 2, x + w - 1, y + 2, 4)
            for i in range(x + 2, x + w, 5):
                px.pset(i, y + 1, 5)
                px.pset(i, y + 3, 5)
        elif t == "FOREST":
            for dx, dy in ((5, 5), (w - 6, 5), (5, h - 6), (w - 6, h - 6)):
                px.circ(x + dx, y + dy, 4, 3)
                px.pset(x + dx - 1, y + dy - 1, 11)

    def draw_lot(self, lot):
        px = self.px
        g = self.g
        x, y, w, h = lot_rect(lot)
        b = g.building_at(lot)
        owned = lot in g.lots
        tlabel = TRAITS[g.trait(lot)]["label"]
        self.draw_lot_base(lot, owned)
        if not owned:
            for i, (dx, dy) in enumerate(((14, 14), (30, 10), (46, 15))):
                px.circ(x + dx, y + dy, 5, 11 if i % 2 else 3)
                px.circb(x + dx, y + dy, 5, 1)
            can = g.lot_adjacent(lot)
            px.rect(x + 2, y + 21, w - 4, 24, 0)
            self.tx_center(x + w // 2, y + 21, tlabel, 7 if can else 13)
            self.tx_center(x + w // 2, y + 32, "$%d" % g.land_price(lot), 10 if can else 13)
            if can:
                px.rectb(x, y, w, h, 10 if self.frame % 30 < 20 else 3)
            return
        fac = g.lot_fac.get(lot)
        if fac == "GARDEN":
            px.rect(x + 4, y + 8, w - 8, h - 22, 11)
            px.circ(x + w // 2, y + h // 2 - 4, 8, 12)
            px.circb(x + w // 2, y + h // 2 - 4, 8, 6)
            for dx, dy in ((10, 12), (w - 10, 12), (12, h - 18), (w - 12, h - 18)):
                px.circ(x + dx, y + dy, 4, 3)
            self.tx_center(x + w // 2, y + 8, "庭園", 1)
            return
        if fac == "PARKING":
            px.rect(x + 3, y + 8, w - 6, h - 22, 5)
            for i in range(5):
                px.line(x + 6 + i * 11, y + 10, x + 6 + i * 11, y + 22, 7)
            for i, col in enumerate((8, 12, 10, 7)):
                if (i + g.day) % 3:
                    px.rect(x + 8 + i * 11, y + 12, 7, 9, col)
            self.tx_center(x + w // 2, y + 24, "駐車場", 7)
            return
        if b is None:
            self.tx_center(x + w // 2, y + 12, tlabel, 3)
            self.tx_center(x + w // 2, y + 24, "空き地", 3)
            return
        top = y + (7 if g.trait(lot) == "STATION" else 3)
        if b.kind == "CHAPEL":
            px.rect(x + 12, top + 6, w - 24, 30, 7)
            px.rect(x + w // 2 - 6, top, 12, 10, 7)
            px.line(x + w // 2, top - 2, x + w // 2, top + 4, 10)
            px.line(x + w // 2 - 2, top, x + w // 2 + 2, top, 10)
            px.rect(x + 14, top + 8, w - 28, 3, 14)
            self.tx_center(x + w // 2, top + 22, "チャペル", 2)
            dx, dy = self.lot_door(lot)
            px.rect(dx - 4, top + 36, 8, 3, 9)
            if b is self.vb:
                px.rectb(x + 10, top - 1, w - 20, 38, 10)
            return
        if b.kind == "MALL":                                 # STEP 19: shopping building
            px.rect(x + 4, top, w - 8, 36, 15)
            for i in range(x + 4, x + w - 4, 8):              # striped awning
                px.rect(i, top + 12, 4, 4, 8)
                px.rect(i + 4, top + 12, 4, 4, 7)
            px.rect(x + 8, top + 18, w - 16, 10, 6)           # shop windows
            for i in range(x + 10, x + w - 10, 12):
                px.rect(i, top + 20, 8, 6, 12 if (i // 12 + self.frame // 30) % 3 else 10)
            self.tx_center(x + w // 2, top + 1, b.name, 4)
            dx, dy = self.lot_door(lot)
            px.rect(dx - 4, top + 36, 8, 3, 9)
            if b is self.vb:
                px.rectb(x + 3, top - 1, w - 6, 38, 10)
            return
        main = b.is_main()
        wall, roof = (7, 8) if main else (6, 5)
        px.rect(x + 4, top, w - 8, 36, wall)
        px.rect(x + 6, top + 2, w - 12, 10, roof)
        for i in range(min(b.floors, 7)):
            px.rect(x + 8 + i * 7, top + 15, 4, 4, 12 if i <= g.max_floor(b) else 13)
        self.tx_center(x + w // 2, top + 22, b.name, 0)
        occ, n, dirty = g.building_stats(b)
        self.tx_center(x + w // 2, top + 2, "%d/%d" % (occ, n), 7)
        dx, dy = self.lot_door(lot)
        px.rect(dx - 4, top + 36, 8, 3, 9)
        if b is self.vb:
            px.rectb(x + 3, top - 1, w - 6, 38, 10)

    # ---------------- HUD / log / menu ----------------
    def draw_hud(self):
        px = self.px
        g = self.g
        px.rect(0, 0, W, MY, 0)
        stars = "★" * g.star + "☆" * (4 - g.star)
        _, _, se_col, se_label = g.season_info()
        wd = g.weekday()
        y1, y2, y3 = 1, 14, 27
        wt = WEATHERS[g.weather_at()]
        rk = g.rokuyo()
        mo = g.month()
        x = 2
        for text, col in (("%d日目(%s)" % (g.day, g.weekday_label()),
                           8 if wd in ("FRI", "SAT") else 7),
                          (wt["label"], wt["color"]),
                          (rk, ROKUYO_COL.get(rk, 7)),
                          ("%d月(%s)" % (mo, se_label), 14 if mo == 6 else se_col),
                          ("%s %s" % (t_to_clock(g.t), "停止" if self.paused else "x%d" % self.speed),
                           10 if self.paused else 7)):
            self.tx(x, y1, text, col)
            x += text_width(text) + 5
        art.sun_moon(px, x, y1 + 1, g.t, self.frame)
        self.tx(W - 92, y1, stars, 10)
        self.tx(W - 50, y1, "評%.1f" % g.rep, 11 if g.rep >= 50 else 8)
        self.tx(2, y2, "資金 $%d" % g.cash, 10 if g.cash >= 0 else 8)
        dcol = 8 if g.over_limit_nights else (9 if g.debt > 0 else 13)
        self.tx(74, y2, "借入 $%d/%d" % (g.debt, g.credit_limit()), dcol)
        p = g.prices
        self.tx(170, y2, "S%d D%d T%d SU%d" % (p["SINGLE"], p["DOUBLE"], p["TWIN"],
                                              p["SUITE"]), 7)
        today = bk.today_bookings(g)
        phase = (self.frame // 90) % 2
        if today and phase == 0:
            self.tx(2, y3, "本日の予約：%s" % today[0].title, 10)
        elif mo == 6 and g.has_venue() and phase == 1:
            self.tx(2, y3, "♪ ジューンブライドの季節：挙式の依頼が増えます", 14)
        elif g.star < 3:
            self.tx(2, y3, "次の★：" + STAR_GOALS[g.star + 1][3], 6)
        elif g.star == 3:
            k = rs.best_route(g)
            self.tx(2, y3, "★4へ：4つの道から1つ　最も近い：%s %d%%" % (
                ROUTES[k]["short"], rs.route_progress(g, k) * 100), 6)
        elif g.route:
            self.tx(2, y3, "★4「%s」" % ROUTES[g.route]["label"], 10)

    def draw_log(self):
        px = self.px
        g = self.g
        y = MB + 2
        px.rect(0, MB + 1, W, H - MB, 0)
        msgs = g.msgs[-3:]
        if self.paused and self.frame % 40 < 28:
            self.tx(W - 70, y, "一時停止中", 10)
        for i, m in enumerate(msgs):
            self.tx(2, y + i * LINE_H - 1, m, 7 if i == len(msgs) - 1 else 13)
        self.draw_toolbar()

    def draw_cols(self, x, y, line, cols, col, title):
        parts = line.split("\t")
        for i, part in enumerate(parts):
            cx = x + (cols[i] if i < len(cols) else cols[-1] + 40 * (i - len(cols) + 1))
            self.tx(cx, y, part, col)
            if cx + text_width(part) > MENU_X + MENU_W - 4:
                self.overflow.append((title, part))

    def draw_menu(self, m):
        px = self.px
        x, y, w, h, iy = self.menu_rect(m)
        if getattr(m, "title_screen", False):
            px.rect(x, y, w, h, 0)
            px.rectb(x, y, w, h, 10)
            for i, (label, ok, _) in enumerate(m.items):
                yy = iy + i * (LINE_H + 4)
                if i == m.sel:
                    px.rect(x + 2, yy - 2, w - 4, LINE_H + 2, 5)
                self.tx_center(W // 2, yy, label, (10 if i == m.sel else 7) if ok else 13)
            return
        px.rect(x, y, w, h, 0)
        px.rectb(x, y, w, h, 10 if m.modal else 7)
        self.tx(x + 5, y + 3, m.title, 8 if m.title.startswith("!!") else 10)
        if not m.modal:
            bx, by, bw, bh = self.close_btn_rect(m)
            mx, my = px.mouse_x, px.mouse_y
            hot = bx <= mx < bx + bw and by <= my < by + bh
            px.rect(bx, by, bw, bh, 8 if hot else 1)
            self.tx(bx + 3, by, "x", 7)
        yy = y + 18
        for line in m.info:
            col = 8 if line.startswith("!!") else (10 if line.startswith("★") else 6)
            self.draw_cols(x + 6, yy, line, m.cols, col, m.title)
            yy += LINE_H
        if m.info:
            yy += 4
        rows = self.menu_rows(m)
        self.keep_visible(m)
        y0 = yy
        for i in range(m.top, min(len(m.items), m.top + rows)):
            label, ok, _ = m.items[i]
            if i == m.sel:
                px.rect(x + 2, yy - 1, w - 4, LINE_H, 5)
                self.tx(x + 4, yy, ">", 10)
            self.draw_cols(x + 14, yy, label, m.cols, 7 if ok else 13, m.title)
            yy += LINE_H
        if len(m.items) > rows:                      # scroll bar
            bh = rows * LINE_H
            px.rect(x + w - 5, y0, 3, bh, 1)
            th = max(6, bh * rows // len(m.items))
            ty = y0 + (bh - th) * m.top // max(1, len(m.items) - rows)
            px.rect(x + w - 5, ty, 3, th, 13)

    def draw_banner(self, title, lines, col):
        px = self.px
        h = 24 + len(lines) * LINE_H
        y = (H - h) // 2
        px.rect(30, y, W - 60, h, 0)
        px.rectb(30, y, W - 60, h, col)
        self.tx(40, y + 5, title, col)
        for i, l in enumerate(lines):
            self.tx(40, y + 20 + i * LINE_H, l, 7)
