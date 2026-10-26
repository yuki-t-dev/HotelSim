# ============================================================
# data.py  -  all tunable tables and geometry
#   * Add a facility  -> add one entry to FACILITIES (+ BUILD_ORDER)
#   * Add a job       -> add one entry to ROLES
#   * Add a building  -> add one entry to BUILDINGS
# ============================================================

# ------------------------------------------------------------
# screen / floor-plan geometry (top-down view)
# ------------------------------------------------------------
W, H = 512, 288                 # STEP 14: wider screen
LINE_H = 12
MY = 40
MB = 220
PANEL_W = 64
SITE_BTN_H = 24
FLOOR_Y0 = MY + 26
FLOOR_BTN_H = 22
CORR_TOP = MY + 82
CORR_BOT = MY + 98
CORR_Y = MY + 90
SX0 = PANEL_W + 24
SW = 68                         # slot width (72 -> 68 in STEP 14)
COLS = 3                        # default columns per row (main building)
SLOTS = 6
ANNEX_COLS = 6                  # STEP 14: annex = 6 x 2 = 12 slots per floor
TOP_Y0, TOP_Y1 = MY + 2, CORR_TOP - 1
BOT_Y0, BOT_Y1 = CORR_BOT + 1, MB - 1
DOOR_W = 14
STAIR_X = PANEL_W + 11
ENTRANCE_X = W - 6
MAX_FLOOR = 6
LOBBY_RESERVED = (0, 1)

# ------------------------------------------------------------
# difficulty / save (STEP 11)
# ------------------------------------------------------------
DIFFICULTY = {
    "EASY":   dict(label="かんたん", cash=6000, demand=1.15, incident=0.6, credit=1.5,
                   text="客多め・トラブル少なめ"),
    "NORMAL": dict(label="ふつう", cash=3000, demand=1.0, incident=1.0, credit=1.0,
                   text="標準の難しさ"),
    "HARD":   dict(label="むずかしい", cash=1800, demand=0.9, incident=1.4, credit=0.7,
                   text="客少なめ・トラブル多め"),
}
DIFF_ORDER = ["EASY", "NORMAL", "HARD"]
SAVE_SLOTS = 3
SAVE_VERSION = 20

# ------------------------------------------------------------
# site map
# ------------------------------------------------------------
SITE_COLS, SITE_ROWS = 4, 3
MAIN_LOT = (1, 1)
START_LOTS = [(1, 1), (2, 1)]
LOT_W, LOT_H, LOT_GAP = 106, 54, 4
LOT_X0 = PANEL_W + 4
LOT_Y0 = MY + 2
LAND_BASE = 600
LAND_STEP = 500
OUT_BASE = 40
OUT_PER_LOT = 45
DEMOLISH_REFUND = 0.25

BUILDINGS = {
    "MAIN":   dict(label="本館", floors=MAX_FLOOR + 1, cost=0, star=1, upkeep=0, cols=3),
    "ANNEX":  dict(label="別館", floors=4, cost=3500, star=2, upkeep=30, cols=ANNEX_COLS,
                   text="4階建て・1フロア12枠の客室棟（客室・大浴場・スパなど）"),
    "MALL":   dict(label="商業棟", floors=3, cost=3000, star=2, upkeep=25, cols=ANNEX_COLS,
                   text="3階建て・1フロア12枠。飲食店・売店・テナント用（客室なし）"),
    "CHAPEL": dict(label="チャペル", floors=1, cost=4000, star=2, upkeep=30, fixed=True, cols=3,
                   text="洋式の結婚式場（挙式の予約が入る）"),
}
SITE_BUILD = ["ANNEX", "MALL", "CHAPEL"]

# ------------------------------------------------------------
# lot traits / outdoor facilities / walkways / weather
# ------------------------------------------------------------
LOT_TRAITS = {
    (0, 0): "FOREST", (1, 0): "STATION", (2, 0): "STATION", (3, 0): "FOREST",
    (0, 1): "NORMAL", (1, 1): "NORMAL", (2, 1): "NORMAL", (3, 1): "NORMAL",
    (0, 2): "OCEAN", (1, 2): "OCEAN", (2, 2): "OCEAN", (3, 2): "OCEAN",
}
TRAITS = {
    "NORMAL":  dict(label="普通", extra=0, text="特になし"),
    "STATION": dict(label="駅前", extra=300, text="ビジネス客が好む。駐車場の効果2倍"),
    "OCEAN":   dict(label="海側", extra=600, text="海の見える部屋は料金+20%。観光客が大喜び"),
    "FOREST":  dict(label="森", extra=-200, text="静かな森。庭園の効果2倍"),
}
OCEAN_PRICE = 1.2
OCEAN_SAT = {"TOURIST": 1.2, "BUSINESS": 0.3}

LOT_FACILITIES = {
    "GARDEN": dict(label="庭園", cost=900, star=1, upkeep=6,
                   text="隣の建物の満足度UP。チャペルの隣なら挙式も華やか"),
    "PARKING": dict(label="駐車場", cost=700, star=1, upkeep=4,
                    text="来客が増える（特にビジネス客）"),
}
GARDEN_SAT = 0.5
PARKING_DEMAND = 0.08
WALKWAY_COST = 500

WEATHERS = {
    "SUN":   dict(label="晴", color=10, demand=1.05),
    "CLOUD": dict(label="曇", color=13, demand=1.0),
    "RAIN":  dict(label="雨", color=12, demand=0.9),
    "SNOW":  dict(label="雪", color=7, demand=0.85),
}
SEASON_WEATHER = {
    "SPRING": {"SUN": 5, "CLOUD": 3, "RAIN": 2},
    "SUMMER": {"SUN": 5, "CLOUD": 2, "RAIN": 3},
    "AUTUMN": {"SUN": 5, "CLOUD": 3, "RAIN": 2},
    "WINTER": {"SUN": 4, "CLOUD": 3, "RAIN": 1, "SNOW": 2},
}
WET_SAT = -1.2
SNOW_SLOW = 1.7

# ------------------------------------------------------------
# room types / prices
# ------------------------------------------------------------
ROOM_KINDS = ["SINGLE", "DOUBLE", "TWIN", "SUITE"]
ROOM_TIER = {"SINGLE": 1, "DOUBLE": 2, "TWIN": 2, "SUITE": 3}
ROOM_TAG = {"SINGLE": "S", "DOUBLE": "D", "TWIN": "T", "SUITE": "SU"}
FAIR_MULT = {"SINGLE": 1.0, "DOUBLE": 1.4, "TWIN": 1.4, "SUITE": 3.0}
PRICE_START = {"SINGLE": 50, "DOUBLE": 70, "TWIN": 70, "SUITE": 150}
PRICE_STEP = {"SINGLE": 5, "DOUBLE": 5, "TWIN": 5, "SUITE": 10}
PRICE_RANGE = {"SINGLE": (20, 300), "DOUBLE": (30, 400), "TWIN": (30, 400),
               "SUITE": (60, 900)}
ROOM_WANT = {
    "BUSINESS": {"SINGLE": 7, "DOUBLE": 2, "TWIN": 1},
    "TOURIST":  {"SINGLE": 1, "DOUBLE": 4, "TWIN": 4},
}
SUITE_WANT = {"TOURIST": 0.14, "BUSINESS": 0.05}

# ------------------------------------------------------------
# time / speed   (1 day = 2400 ticks = 06:00 -> 24:00, 1 h = 133 ticks)
# ------------------------------------------------------------
WALK = 0.8
STAIR_T = 25
DAY_TICKS = 2400
CHECKOUT_RANGE = (380, 700)
CLEAN_T = 220
CHECKIN_T = 70
DESK_PATIENCE = 600
COOK_PREP = 250


def clock_to_t(h, m=0):
    return int(round((h - 6 + m / 60) / 18 * DAY_TICKS))


# ------------------------------------------------------------
# facilities
# ------------------------------------------------------------
FOOD_COMMON = dict(category="food", lobby_ok=True, annex_ok=False, mall_ok=True, max_count=1,
                   roles={"COOK": 2, "CLEANER": 1})
ROOM_COMMON = dict(category="room", lobby_ok=False, annex_ok=True, max_count=None)
WED_COMMON = dict(category="wedding", lobby_ok=True, annex_ok=False, max_count=1, roles={})
FACILITIES = {
    "SINGLE": dict(ROOM_COMMON, label="シングル", cost=350, star=1, size=1, upkeep=5,
                   clean_mult=0.9),
    "DOUBLE": dict(ROOM_COMMON, label="ダブル", cost=450, star=1, size=1, upkeep=6,
                   clean_mult=1.0),
    "TWIN": dict(ROOM_COMMON, label="ツイン", cost=500, star=1, size=1, upkeep=7,
                 clean_mult=1.1),
    "SUITE": dict(ROOM_COMMON, label="スイート", cost=1200, star=2, size=2, upkeep=15,
                  clean_mult=1.6, bed_dx=20),
    "CAFE": dict(FOOD_COMMON, label="カフェ", short="カフェ", cost=600, star=1, size=1,
                 upkeep=12, serve=clock_to_t(7, 30), meal="朝食",
                 per_cook=10, price=8, dirt=1.0, cook_skill=1, color=9, lunch_price=9),
    "WASHOKU": dict(FOOD_COMMON, label="和食", short="和食", cost=1500, star=2, size=2,
                    upkeep=30, serve=clock_to_t(19), meal="会席",
                    per_cook=5, price=30, dirt=1.2, cook_skill=2, color=4, lunch_price=14),
    "BUFFET": dict(FOOD_COMMON, label="ビュッフェ", short="ビュフェ", cost=1100, star=2,
                   size=2, upkeep=25, serve=clock_to_t(19, 30), meal="バイキング",
                   per_cook=14, price=12, dirt=2.6, cook_skill=1, color=14),
    "BAR": dict(FOOD_COMMON, label="バー", short="バー", cost=800, star=2, size=1,
                upkeep=15, serve=clock_to_t(22), meal="ドリンク",
                per_cook=10, price=10, dirt=0.8, cook_skill=1, color=2),
    # STEP 18: new restaurants  (lunch=True -> can open for lunch at 12:00)
    "CHINESE": dict(FOOD_COMMON, label="中華", short="中華", cost=1300, star=2, size=2,
                    upkeep=25, serve=clock_to_t(18, 45), meal="中華コース",
                    per_cook=8, price=18, dirt=1.6, cook_skill=1, color=8,
                    lunch_price=10, text="円卓で大人数に強い。団体客が好む"),
    "ITALIAN": dict(FOOD_COMMON, label="イタリアン", short="伊料理", cost=1000, star=2, size=1,
                    upkeep=18, serve=clock_to_t(19, 15), meal="パスタ",
                    per_cook=6, price=22, dirt=1.1, cook_skill=1, color=11,
                    lunch_price=12, text="カップル（ダブルの客）が大好き"),
    "FRENCH": dict(FOOD_COMMON, label="フレンチ", short="仏料理", cost=2500, star=3, size=2,
                   upkeep=40, serve=clock_to_t(19, 45), meal="フルコース",
                   per_cook=4, price=45, dirt=1.0, cook_skill=3, color=7,
                   text="最高級。VIPと有名人が喜ぶ。料理人★★★が必要"),
    "MEETING": dict(label="会議室", short="会議室", cost=800, star=2, size=1, upkeep=10,
                    category="hall", lobby_ok=True, annex_ok=False, max_count=None,
                    roles={}, seats=10),
    "BANQUET": dict(label="宴会場", short="宴会場", cost=2200, star=2, size=2, upkeep=30,
                    category="hall", lobby_ok=True, annex_ok=False, max_count=1,
                    roles={"COOK": 2, "CLEANER": 1}, serve=clock_to_t(18, 30),
                    meal="宴会料理", per_cook=12, dirt=1.5, cook_skill=1, color=10),
    "SHRINE": dict(WED_COMMON, label="神殿", cost=3000, star=2, size=2, upkeep=25,
                   text="神前式の会場（館内なので雨でも安心）"),
    "YUINO": dict(WED_COMMON, label="結納の間", cost=900, star=2, size=1, upkeep=8,
                  text="両家の結納。成功すると挙式の予約につながる"),
    "DRESS": dict(WED_COMMON, label="衣装室", cost=700, star=2, size=1, upkeep=8,
                  text="花嫁の支度部屋。ないと婚礼の評価が下がる"),
    "CHAPEL_HALL": dict(label="礼拝堂", cost=0, star=2, size=3, upkeep=0, category="wedding",
                        lobby_ok=False, annex_ok=False, max_count=None, roles={},
                        buildable=False),
    "ONSEN": dict(label="大浴場", short="大浴場", cost=2500, star=2, size=2, upkeep=25,
                  category="resort", lobby_ok=True, annex_ok=True, max_count=1,
                  roles={"CLEANER": 1}, dirt=0.9, cap=16, color=12,
                  text="温泉の大浴場。海側・森の別館なら露天風呂に"),
    "SPA": dict(label="スパ", short="スパ", cost=1200, star=2, size=1, upkeep=15,
                category="resort", lobby_ok=True, annex_ok=True, max_count=1,
                roles={"CLEANER": 1}, dirt=1.2, cap=6, price=25, color=14,
                text="エステとマッサージ（1回$25）。VIPと観光客が好む"),
    # STEP 19: shops
    "SHOP": dict(label="売店", short="売店", cost=500, star=1, size=1, upkeep=4,
                 category="shop", lobby_ok=True, annex_ok=True, mall_ok=True,
                 max_count=None, roles={},
                 text="店の前を通る人が買っていく。人通りの多い所ほど売れる"),
    "TENANT": dict(label="テナント区画", short="テナント", cost=1800, star=2, size=2, upkeep=5,
                   category="tenant", lobby_ok=True, annex_ok=False, mall_ok=True,
                   max_count=None, roles={},
                   text="ブランド店に貸す区画。家賃が毎日入る（スタッフ不要）"),
    # STEP 20: leisure
    "POOL": dict(label="プール", short="プール", cost=3000, star=2, size=2, upkeep=30,
                 category="leisure", lobby_ok=True, annex_ok=True, mall_ok=True, max_count=1,
                 roles={"GUARD": 1, "CLEANER": 1}, dirt=0.5,
                 text="夏に大人気（冬は閉鎖）。外来客はデイパス$12。監視員が必要"),
    "GYM": dict(label="ジム", short="ジム", cost=1500, star=2, size=1, upkeep=12,
                category="leisure", lobby_ok=True, annex_ok=True, mall_ok=True, max_count=1,
                roles={"CLEANER": 1}, dirt=0.3,
                text="ビジネス客が喜ぶ。地元の会員から毎日会費が入る"),
    "SECROOM": dict(label="警備室", cost=700, star=1, size=1, upkeep=8, category="security",
                    lobby_ok=True, annex_ok=True, mall_ok=True, max_count=None, roles={"GUARD": 2},
                    text="警備員がモニターで防犯カメラを監視する部屋"),
    "STAFFROOM": dict(label="休憩室", cost=600, star=1, size=1, upkeep=8,
                      category="staff", lobby_ok=True, annex_ok=True, mall_ok=True,
                      max_count=None,
                      seats=3, roles={}),
}
BUILD_ORDER = ["SINGLE", "DOUBLE", "TWIN", "SUITE", "CAFE", "WASHOKU", "BUFFET", "BAR",
               "CHINESE", "ITALIAN", "FRENCH",
               "MEETING", "BANQUET", "SHRINE", "YUINO", "DRESS", "ONSEN", "SPA",
               "SHOP", "TENANT", "POOL", "GYM", "SECROOM", "STAFFROOM"]
FOOD_KINDS = [k for k in BUILD_ORDER if FACILITIES[k]["category"] == "food"]

# ------------------------------------------------------------
# hygiene / food poisoning
# ------------------------------------------------------------
HYGIENE_DAILY_DROP = 4
HYGIENE_WARN = 60
HYGIENE_DANGER = 45
POISON_MAX_P = 0.45
POISON_CLOSE_DAYS = 3
POISON_REP = 8
POISON_COMP = 40
DEEP_CLEAN_COST = 150
FAC_CLEAN_T = 160
FAC_CLEAN_GAIN = 22

# ------------------------------------------------------------
# bookings
# ------------------------------------------------------------
OFFER_CHANCE = 0.35
OFFER_LEAD = (3, 6)
MAX_BOOKINGS = 6
MEET_ARRIVE = clock_to_t(7, 45)
MEET_T = clock_to_t(10)
MEET_END = clock_to_t(17)
GROUP_ARRIVE = (clock_to_t(14, 30), clock_to_t(16, 30))
PARTY_ARRIVE = clock_to_t(16)
PARTY_END = clock_to_t(21)
RENTAL_PRICE = 80
RENTAL_END = clock_to_t(16)
COMPANIES = ["ハママツ光学", "イワタ電機", "テンリュウ商事", "エンシュウ製作所",
             "サナル物産", "ミクリヤ工業", "カケガワ化成", "フクデ食品"]
CONF_NAMES = ["カンファレンス", "研修会", "株主総会", "商談会"]
PARTY_NAMES = ["結婚記念パーティー", "還暦祝い", "同窓会", "創立記念パーティー"]
FAMILY_PARTY = ["結婚記念パーティー", "還暦祝い"]
FAMILIES = ["スズキ", "ヤマダ", "タナカ", "ササキ", "マツシマ", "イトウ", "ワタナベ",
            "ナカムラ", "コバヤシ", "カトウ", "ヨシダ", "ヤマモト"]
SEASON_PARTY = {"SPRING": "歓迎会", "SUMMER": "納涼会", "AUTUMN": "収穫祭", "WINTER": "忘年会"}
VIP_CONF_CHANCE = 0.3
VIP_CONF_GUARDS = 2
VIP_CONF_PAY = 1.25

# ------------------------------------------------------------
# weddings
# ------------------------------------------------------------
ROKUYO = ["先勝", "友引", "先負", "仏滅", "大安", "赤口"]
ROKUYO_WED = {"大安": 3.0, "友引": 1.6, "先勝": 1.0, "先負": 0.8, "赤口": 0.5, "仏滅": 0.15}
ROKUYO_PAY = {"大安": 1.2, "友引": 1.1, "先勝": 1.0, "先負": 1.0, "赤口": 0.95, "仏滅": 0.7}
WED_CHANCE = 0.45
WED_SEASON = {"SPRING": 1.2, "SUMMER": 1.3, "AUTUMN": 1.3, "WINTER": 0.7}
WED_LEAD = (5, 10)
WED_ARRIVE = clock_to_t(9, 30)
CEREMONY_T = clock_to_t(11)
TO_RECEPTION_T = clock_to_t(11, 30)
RECEPTION_T = clock_to_t(14)
WED_END = clock_to_t(16, 30)
WED_STAY_ARRIVE = (clock_to_t(14), clock_to_t(15, 30))
YUINO_ARRIVE = clock_to_t(9)
YUINO_T = clock_to_t(11)
YUINO_END = clock_to_t(14)
GARDEN_WED_BONUS = 0.15
JUNE_DAY_WEIGHT = 3.0
JUNE_OFFER = 2.2
JUNE_PAY = 1.15
WED_OFFER_P = 0.28          # STEP 13: daily chance of a wedding offer (own line)
YUINO_OFFER_P = 0.10
CEREMONY_ONLY_PAY = 0.55    # "ceremony only" plan (no banquet hall) pays less

# ------------------------------------------------------------
# demand control (STEP 13)
# ------------------------------------------------------------
OCC_MAX = 1.0               # max share of rooms filled by the base demand
DEMAND_CAP = 1.2            # walk-ins per free room tonight (hard cap)
QUEUE_PER_FRONT = 3         # arrivals wait outside when the desk line is longer
QUEUE_BASE = 2
QUEUE_RETRY = 80            # ticks
ANGRY_REP_CAP = 4.0         # max reputation lost per day by guests leaving the desk
HOT_DEMAND = 1.25

# ------------------------------------------------------------
# room holds (STEP 16)
#   CELEB  : suite kept for a celebrity (auto)
#   GROUP  : rooms kept for a booked group (conference / wedding guests)
#   BRIDE  : suite kept for the bride and groom (wedding with reception)
#   PLAYER : kept by the player for VIPs (until released)
# ------------------------------------------------------------
HOLD_LABEL = {"CELEB": "有名人", "GROUP": "団体", "BRIDE": "新郎新婦", "PLAYER": "VIP用"}
HOLD_COLOR = {"CELEB": 10, "GROUP": 12, "BRIDE": 14, "PLAYER": 9}
MOVE_COMP = 100             # apology money when a guest is asked to change rooms
COUPLE_REP = 1.0            # extra rep when the couple stays in the bridal suite

# ------------------------------------------------------------
# upgrades (STEP 17)   level 1 -> 2 -> 3
#   cost is a share of the facility's build cost (front desk: fixed $)
# ------------------------------------------------------------
UPGRADES = {
    "ROOM":  [None,
              dict(label="内装を改装", rate=0.6, text="満足度+0.5（きれいな内装）"),
              dict(label="高級家具を入れる", rate=1.0,
                   text="満足度+0.8・料金が自動で+15%")],
    "ONSEN": [None,
              dict(label="露天風呂を造る", rate=0.6, text="どこに建てても露天風呂に"),
              dict(label="サウナを追加", rate=0.8, text="定員+6・満足度+0.5（冬は+1.0）")],
    "POOL":  [None,
              dict(label="屋内プールにする", rate=0.7, text="一年中営業・定員+6・雨でもOK"),
              dict(label="ナイトプール", rate=0.6, text="20:00から夜の営業（1人$18）")],
    "GYM":   [None,
              dict(label="マシンを増やす", rate=0.8, text="会員の上限 30→50人"),
              dict(label="スタジオを併設", rate=1.0, text="会員の上限 50→80人")],
    "FRONT": [None,
              dict(label="自動チェックイン機", cost=1500,
                   text="機械が人手なしで受付（ビジネス客が使う）"),
              dict(label="コンシェルジュ", cost=3500,
                   text="VIP・有名人・予約客は列に並ばず部屋へ案内")],
}
ROOM_LV_SAT = [0.0, 0.0, 0.5, 0.8]
ROOM_LV_PRICE = [1.0, 1.0, 1.0, 1.15]
SAUNA_CAP = 6
SAUNA_SAT = 0.5
KIOSK_T = 120               # ticks per check-in at the kiosk
KIOSK_UPKEEP = 10
CONCIERGE_UPKEEP = 25
CONCIERGE_SAT = 0.6

# ------------------------------------------------------------
# restaurants for outside guests (STEP 18)
#   OUTSIDE[kind] = (lunch, dinner) base number of non-staying diners
# ------------------------------------------------------------
LUNCH_T = clock_to_t(12)
DINNER_KINDS = ["WASHOKU", "BUFFET", "CHINESE", "ITALIAN", "FRENCH"]
OUTSIDE = {"CAFE": (7, 0), "WASHOKU": (5, 3), "BUFFET": (0, 2), "BAR": (0, 3),
           "CHINESE": (8, 5), "ITALIAN": (7, 5), "FRENCH": (0, 3)}
DROPIN_P = 0.5              # turned-away guests who still stay for dinner
OUTSIDE_COLOR = 4

# ------------------------------------------------------------
# shops / tenants (STEP 19)
# ------------------------------------------------------------
SHOP_P = {"TOURIST": 0.22, "BUSINESS": 0.10, "VISIT": 0.08}   # buy chance when passing
SHOP_PRICE = (4, 9)
UMBRELLA_PRICE = 10
SHOPPER_COLOR = 13          # outside shoppers (grey coats)
SHOPPER_BASE = 2
TENANT_OFFER_P = 0.5
TENANT_WARN = 2             # days below the line -> warning
TENANT_LEAVE = 4            # days below the line -> moves out
BRAND_ORDER = ["SELECT", "MODE", "JEWEL"]       # cheap -> luxury
BRANDS = {
    "SELECT": dict(label="セレクトショップ・アオイ", short="アオイ", kind="雑貨・服",
                   star=2, rep=60, rent=50, bonus=10, pull=2, color=12),
    "MODE":   dict(label="ミラノ・モード", short="MILANO", kind="ファッション",
                   star=3, rep=70, rent=100, bonus=30, pull=3, color=2),
    "JEWEL":  dict(label="ルミエール宝飾", short="LUMIERE", kind="宝飾",
                   star=3, rep=80, suites=3, rent=160, bonus=60, pull=2, color=10),
}
TENANT_SAT = {"VIP": 0.6, "TOURIST": 0.3}

# ------------------------------------------------------------
# pool / gym (STEP 20)
# ------------------------------------------------------------
POOL_T = clock_to_t(16)
POOL_OPEN = (clock_to_t(10), clock_to_t(18))
NIGHT_POOL_T = clock_to_t(20)
POOL_SEASON = {"SPRING": 0.8, "SUMMER": 2.5, "AUTUMN": 0.6, "WINTER": 0.0}
POOL_CAP = 20
DAYPASS = 12
NIGHT_PASS = 18
POOL_OUT_BASE = 6
POOL_ACCIDENT_P = 0.12
POOL_ACCIDENT_REP = 6
POOL_CLOSE_DAYS = 2
POOL_SAT = {"TOURIST": 1.0, "BUSINESS": 0.5}
GYM_SAT = 0.6
GYM_FEE = 4                 # per member per day
GYM_CAP = [0, 30, 50, 80]   # by level
GYM_GROW = 3                # members joining / leaving per day
LEISURE_COLOR = 12           # raw demand / capacity above this -> "raise prices!" hint

# ------------------------------------------------------------
# security
# ------------------------------------------------------------
CAMERA_COST = 150
CAMERA_UPKEEP = 2
PATROL_SEC = 0.35
CAM_SEC_WATCHED = 0.45
CAM_SEC_ALONE = 0.15
SEC_MAX = 0.9
INCIDENT_BASE = 0.05
INCIDENT_PER_GUEST = 0.008
PATROL_WAIT = 120
INCIDENTS = {
    "THEFT": dict(label="盗難", weight=4),
    "DRUNK": dict(label="酔客の騒ぎ", weight=3),
    "FIRE":  dict(label="ボヤ", weight=1),
    "PROWLER": dict(label="不審者", weight=2),
}
THEFT_COMP = 120
FIRE_COST = 400
FIRE_DAYS = 3

# ------------------------------------------------------------
# resort / reviews / rival
# ------------------------------------------------------------
BATH_T = clock_to_t(20, 30)
ONSEN_SAT = {"TOURIST": 1.0, "BUSINESS": 0.5}
OPEN_AIR_SAT = 0.6
SPA_SAT = 0.8
REVIEW_KEEP = 30
REVIEW_N = 20
REVIEW_DEMAND = 0.08
RIVAL_DAY = 22
RIVAL_NAME = "ホテル・ゴールデンベイ"
RIVAL_REP0 = 58
PRICE_WAR_CUT = 0.85
PRICE_WAR_OK = 0.9

# ------------------------------------------------------------
# jobs
# ------------------------------------------------------------
ROLES = {
    "FRONT":   dict(label="フロント", wage=35, color=9,  post="DESK",   post_max=3),
    "CLEANER": dict(label="清掃係", wage=30, color=11, post="FLOOR",  post_max=None),
    "COOK":    dict(label="料理人", wage=40, color=7,  post="FAC",    post_max=None),
    "GUARD":   dict(label="警備員", wage=32, color=5,  post="PATROL", post_max=3),
}
SKILL_SPEED = [1.0, 1.35, 1.7]
SKILL_WAGE = [1.0, 1.4, 1.8]
EXP_LV = [2500, 7000]
BREAK_RULES = [60, 70, 80, 90]

# ------------------------------------------------------------
# progression
# ------------------------------------------------------------
STAR_GOALS = {
    2: (6, None, 55, "客室6・評判55"),
    3: (12, "dinner", 70, "客室12・夕食の店（和食・中華など）・評判70"),
}
ROUTES = {
    "LODGING": dict(label="名門ホテル", short="宿泊", color=10),
    "WEDDING": dict(label="憧れの式場", short="婚礼", color=14),
    "MICE":    dict(label="ビジネスの拠点", short="MICE", color=12),
    "RESORT":  dict(label="癒しのリゾート", short="リゾート", color=11),
}
ROUTE_ORDER = ["LODGING", "WEDDING", "MICE", "RESORT"]
FLOOR_LIMIT = {1: 2, 2: 4, 3: 6, 4: 6}

# ------------------------------------------------------------
# calendar  (day 1 = MON, SPRING / March)
# ------------------------------------------------------------
WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
WEEKDAY_LABEL = ["月", "火", "水", "木", "金", "土", "日"]
DAY_DEMAND = [0.85, 0.85, 0.90, 0.95, 1.25, 1.35, 0.70]
DAY_BIZ = [0.70, 0.70, 0.70, 0.65, 0.40, 0.15, 0.30]
SEASON_DAYS = 14
SEASONS = [
    ("SPRING", 1.00, 14, "春"),
    ("SUMMER", 1.25, 10, "夏"),
    ("AUTUMN", 1.05, 9, "秋"),
    ("WINTER", 0.80, 12, "冬"),
]
SEASON_FIRST_MONTH = {"SPRING": 3, "SUMMER": 6, "AUTUMN": 9, "WINTER": 12}

# ------------------------------------------------------------
# guest types
# ------------------------------------------------------------
GUEST_TYPES = {
    "BUSINESS": dict(label="ビジネス", color=1, nights=[1, 1, 1, 2],
                     arrive=(1200, 1800), patience=0.75, food_w=0.6,
                     food_pref={"CAFE": 4, "BAR": 4, "BUFFET": 1, "WASHOKU": 1,
                                "CHINESE": 2, "ITALIAN": 1, "FRENCH": 1}),
    "TOURIST": dict(label="観光", color=12, nights=[1, 2, 2, 3],
                    arrive=(900, 1600), patience=1.2, food_w=1.4,
                    food_pref={"WASHOKU": 4, "BUFFET": 4, "CAFE": 1, "BAR": 1,
                               "CHINESE": 3, "ITALIAN": 2, "FRENCH": 1}),
}

# ------------------------------------------------------------
# events
# ------------------------------------------------------------
EVENT_CHANCE = 0.40
EVENT_COOLDOWN = 4

NAMES = ["アキ", "ケン", "ユイ", "ハナ", "リン", "ソラ", "レン", "ミオ", "カイ",
         "ナオ", "タク", "エミ", "ユウ", "サキ", "ジョー", "ベン", "マックス", "リア",
         "トム", "サム", "ルカ", "ノア", "エマ", "ミク", "ハル", "コウ", "ユキ",
         "メイ", "ダン", "イヴ", "ゴウ", "リュウ", "ジン", "テツ"]

# ------------------------------------------------------------
# font (Japanese BDF, 10px).  ASCII = 6px wide, others = 10px wide
# ------------------------------------------------------------
FONT_FILES = ["umplus_j10r.bdf", "umplus_j10r.bdf.txt"]


def text_width(s):
    return sum(6 if ord(ch) < 256 else 10 for ch in s)


# ------------------------------------------------------------
# small helpers
# ------------------------------------------------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def approach(v, t, step):
    d = t - v
    if abs(d) <= step:
        return t
    return v + (step if d > 0 else -step)


def t_to_clock(t):
    mins = int(round(t * 18 * 60 / DAY_TICKS))
    return "%02d:%02d" % ((6 + mins // 60) % 24, mins % 60)


def slot_rect(s, cols=COLS):
    col, row = s % cols, s // cols
    x = SX0 + col * SW + 1
    if row == 0:
        return x, TOP_Y0, SW - 2, TOP_Y1 - TOP_Y0
    return x, BOT_Y0, SW - 2, BOT_Y1 - BOT_Y0


def cell_rect(c):
    x, y, w, h = slot_rect(c.s, c.b.cols)
    return x, y, w + SW * (c.w - 1), h


def in_corridor(y):
    return CORR_TOP + 2 <= y <= CORR_BOT - 2


def lot_rect(lot):
    lx, ly = lot
    return (LOT_X0 + lx * (LOT_W + LOT_GAP), LOT_Y0 + ly * (LOT_H + LOT_GAP), LOT_W, LOT_H)


def lot_dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
