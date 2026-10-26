# ============================================================
# PIXEL HOTEL  (STEP 20)  -  hotel management game with Pyxel
#
#   Files
#     main.py     : start the game  ->  python main.py
#     data.py     : tables (facilities, buildings, rooms, jobs, difficulty ...)
#     model.py    : data objects (Building / Cell / Guest / Staff / Visitor)
#     game.py     : game rules + save data (no pyxel, testable headless)
#     events.py   : random events
#     bookings.py : reservations (conference / party / wedding / yuino)
#     security.py : guards, cameras, incidents
#     resort.py   : onsen / spa, reviews, rival hotel, routes to the 4th star
#     shops.py    : kiosk shops, brand tenants, outside shoppers  (STEP 19)
#     leisure.py  : pool and gym                                  (STEP 20)
#     ui.py       : Pyxel title / input / menus / drawing (Japanese)
#     art.py      : time-of-day lighting + pixel-art people     (STEP 12)
#     umplus_j10r.bdf : Japanese font (Pyxel 2.2+)  <- put it in this folder
#     saves/      : created automatically (slot1-3.sav, autosave.sav)
#
#   History
#     STEP 1-3 : rooms, staff, staff room, bank loans
#     STEP 3.x : stairs, top-down view, 2-slot facilities, mouse menus
#     STEP 4   : modules, calendar, guest types, events
#     STEP 5   : restaurants, hygiene, food poisoning      STEP 5.1 : Japanese UI
#     STEP 6   : bookings, meeting room, banquet hall
#     STEP 7   : site map, annex, lot traits, garden / parking, walkway, weather
#     STEP 8   : room types with prices, weddings, rokuyo
#     STEP 9   : months / June bride, guards, cameras, incidents
#     STEP 10  : 4 routes to the 4th star, onsen / spa, reviews, rival, ending
#     STEP 11  : (NEW) title screen, difficulty (3 levels), SAVE / LOAD
#                (3 slots + autosave every morning), tutorial hints
#     STEP 20  : (NEW) POOL & GYM  (Step 12-19 saves still load)
#       * POOL (2 slots): summer x2.5, closed in winter; day pass $12 for outside guests;
#         a guard posted as LIFEGUARD prevents accidents (rep -6, closed 2 days)
#         Lv2 indoor (all year, rain OK) / Lv3 night pool at 20:00 ($18)
#       * GYM (1 slot): business guests love it; local members pay $4 a day
#         (grows with reputation, station lots +20%), Lv2 / Lv3 raise the member cap
#     STEP 19  : SHOPS & TENANTS  (Step 12-18 saves still load)
#       * SHOP (売店, no staff): sells to people walking past its door; the lobby and
#         the shopping building sell best; umbrellas on rainy days
#       * TENANT space (no staff): a brand moves in when its conditions are met,
#         pays rent every night + bonus per VIP / celebrity; leaves if the reputation
#         stays below its line (warning after 2 days, leaves after 4)
#       * MALL (商業棟, 3 floors x 12 slots): restaurants / shops / tenants, no rooms;
#         shoppers from the street enter through its own door
#     STEP 18  : RESTAURANTS  (Step 12-17 saves still load)
#       * CHINESE (groups / tours), ITALIAN (couples in doubles), FRENCH (VIP, cook ★★★)
#       * lunch service at 12:00 (cafe / washoku / chinese / italian), toggle per restaurant
#       * outside diners (not staying): numbers depend on reputation, stars, weekday,
#         weather, parking and station lots; guests turned away may still stay for dinner
#       * outside diners shown on the floor plan and in the daily report
#     STEP 17  : UPGRADES  (Step 12-16 saves still load)
#       * rooms Lv2 renovation (sat +0.5) / Lv3 luxury furniture (sat +0.8, price +15%)
#       * onsen Lv2 open-air bath anywhere / Lv3 sauna (capacity +6, sat +0.5, winter x2)
#       * front desk Lv2 check-in kiosk (business guests, no staff) /
#         Lv3 concierge (VIP / celebrity / booked guests skip the line)
#       * upgrades from the room / onsen / front desk menus, shown on the floor plan
#     STEP 16  : ROOM HOLDS  (Step 12-15 saves still load)
#       * celebrity: a suite is kept as soon as you accept (best security / ocean / floor);
#         if every suite is taken, ask a staying guest to move ($100, rep -1) or decline
#       * group bookings keep real rooms in the morning (same type, close together)
#       * wedding with reception: bridal suite kept, the couple stays the night (rep +1)
#       * player hold: "keep for VIP" from the room menu (only VIPs / celebrities use it)
#       * held rooms show a coloured "予約" plate, are cleaned first, and appear in tooltips
#     STEP 15  : MOUSE-ONLY PLAY  (Step 12-14 saves still load)
#       * icon toolbar at the bottom (tooltips show names only), red dots = attention
#       * pause / x1 / x2 / x4 buttons, clickable status bar (date, cash, prices, stars)
#       * mouse wheel: floors, and scrolling for long menus (scroll bar)
#       * hover tooltips for guests, staff, rooms and facilities
#       * tutorial points at the buttons; no keyboard hints anywhere on screen
#     STEP 14  : WIDE SCREEN 512 x 288  (Step 12-13 saves still load)
#       * annex: 6 x 2 = 12 slots per floor (old annexes are widened on load;
#         lower-row room numbers change, e.g. 004 -> 007)
#       * main building keeps 3 x 2; the free space shows a floor info panel
#       * slot width 72 -> 68, menus centred (max 420 px), wider site lots
#       * annex price $2500 -> $3500, upkeep $20 -> $30 (twice the rooms)
#     STEP 13  : BALANCE + CHAPEL FIX  (Step 12 saves still load)
#       * walk-ins capped at 1.2 x rooms free tonight, base occupancy <= 100%
#       * full house: no reputation loss (shown as lost sales in the report)
#       * desk walk-outs: max reputation loss per day; arrivals wait outside
#         when the desk line is long; booked guests get a priority line
#       * "raise prices!" hint on high-demand days, fair-price notice on star up
#       * "no dinner" penalty only for guests who wanted to eat (restaurant full)
#       * weddings: own offer line (can share a day with meetings),
#         "ceremony only" plan without a banquet hall, offer rate shown in menus
#       * booked rooms are held including rooms still being cleaned
#     STEP 12  : GRAPHICS
#       * time of day: dawn / day / dusk / night colour (palette swap)
#         corridor lamps, bedside lamps, rooms go dark after 22:00 (zZ)
#         site map: sunset sea, street lamps, lit windows of occupied floors
#       * pixel-art people (5x7) with walking animation and facing
#         front = navy suit, cleaner = green + apron, cook = white + toque,
#         guard = blue + cap (+ flashlight at night), bride in a white dress ...
#
#   Controls
#     mouse only (left click = select, right click = back, wheel = floors / scroll)
# ============================================================
from ui import App

if __name__ == "__main__":
    App()
