"""Check-In! game data: the object catalogue, floor finishes, room types, guest types, staff
roles, review lines and the economy. One source of truth for the simulation's numbers (prices,
unlocks, room requirements, budgets, wages, upkeep, supplies...).

Owned by workstream C (simulation and balance, see carts/checkin/CONTRACT.md). Pure data: no
assets are made here. tools/gen_checkin_assets.py imports it and generates gen.akr and
gen/strings.bin from it; run as a script, this file writes the ECONOMY table to
carts/checkin/gen_sim.akr (imported by sim.akr). So after editing it run both:

    python3 tools/checkin_data.py && python3 tools/gen_checkin_assets.py
"""

# use kinds: what an object does for the person using it
USES = ['NONE', 'SLEEP', 'TOILET', 'WASH', 'SHOWER', 'BATH', 'EAT', 'DRINK', 'TV', 'WORK', 'MODEM',
        'LOUNGE', 'MASSAGE', 'SAUNA', 'GYM', 'MEET', 'PLAY', 'SNACK', 'COFFEE', 'CHECKIN', 'CONCIERGE',
        'COOK', 'FRIDGE', 'PASS', 'LAUNDRY', 'DRY', 'LINEN', 'STORE', 'REST', 'LOCKER', 'SIT', 'PHONE',
        'MINIBAR', 'HOTTUB', 'MUSIC', 'KEYS']
U = {n: i for i, n in enumerate(USES)}

# object flags
F_STATION = 1        # needs a staff member on shift
F_OUTDOOR = 2        # may stand outdoors (deck, garden, beach)
F_INDOOR = 4         # may stand indoors
F_VOID = 8           # placed on void tiles (chandelier, skylight)
F_ATRIUM = 16        # stands at the bottom of an atrium (tree, fountain)
F_TRANSPORT = 32     # stairs and elevators
F_WALKABLE = 64      # people walk over it (rugs) - unused
F_WALLPIECE = 128    # door/window/railing: not placed from the catalogue
F_NOISY_NIGHT = 256  # loud at night (jukebox)
F_ROOFTOP = 512      # top floor only (skylight)
F_JOIN = 1024        # segments join (bar counter)
F_TALL = 2048        # placeholder: tall box

TABS = ['Rooms', 'Build', 'Bedroom', 'Bathroom', 'Lobby', 'Dining', 'Service', 'Leisure', 'Decor']
T = {n: i for i, n in enumerate(TABS)}
IO = F_INDOOR | F_OUTDOOR

# key, name, W, D, height (tiles), price, tab, unlock stars, use kind, guest spots, staff spot, noise,
# appeal, flags, placeholder colour
#   spots are (lx, lz) tiles in the object's local frame (front = +z): where a person stands to use it
OBJ = [
    ('bed_single', 'Single bed', 1, 2, 0.6, 300, 'Bedroom', 0, 'SLEEP', [(0, 2)], None, 0, 1, F_INDOOR, (110, 150, 220)),
    ('bed_double', 'Double bed', 2, 2, 0.6, 550, 'Bedroom', 0, 'SLEEP', [(0, 2), (1, 2)], None, 0, 2, F_INDOOR, (90, 130, 210)),
    ('nightstand', 'Nightstand', 1, 1, 0.5, 80, 'Bedroom', 0, 'NONE', [], None, 0, 1, F_INDOOR, (150, 100, 60)),
    ('wardrobe', 'Wardrobe', 1, 1, 2.0, 220, 'Bedroom', 0, 'NONE', [(0, 1)], None, 0, 1, F_INDOOR | F_TALL, (140, 90, 50)),
    ('tv', 'TV set', 1, 1, 1.0, 400, 'Bedroom', 0, 'TV', [(0, 2)], None, 2, 2, F_INDOOR, (60, 60, 70)),
    ('desk', 'Writing desk', 1, 1, 0.8, 180, 'Bedroom', 0, 'WORK', [(0, 1)], None, 0, 1, F_INDOOR, (160, 110, 70)),
    ('chair', 'Chair', 1, 1, 0.9, 60, 'Bedroom', 0, 'SIT', [(0, 1)], None, 0, 1, F_INDOOR | F_OUTDOOR, (170, 120, 80)),
    ('minibar', 'Minibar', 1, 1, 0.8, 350, 'Bedroom', 2, 'MINIBAR', [(0, 1)], None, 1, 2, F_INDOOR, (200, 200, 210)),
    ('floor_lamp', 'Floor lamp', 1, 1, 1.7, 90, 'Decor', 0, 'NONE', [], None, 0, 1, F_INDOOR | F_TALL, (250, 220, 150)),
    ('sofa', 'Sofa', 2, 1, 0.8, 450, 'Bedroom', 1, 'SIT', [(0, 1), (1, 1)], None, 0, 2, F_INDOOR, (200, 90, 90)),
    ('toilet', 'Toilet', 1, 1, 0.8, 150, 'Bathroom', 0, 'TOILET', [(0, 1)], None, 1, 0, F_INDOOR, (240, 240, 245)),
    ('shower', 'Shower', 1, 1, 2.2, 300, 'Bathroom', 0, 'SHOWER', [(0, 1)], None, 1, 1, F_INDOOR | F_TALL, (170, 220, 240)),
    ('bathtub', 'Bathtub', 1, 2, 0.6, 600, 'Bathroom', 1, 'BATH', [(1, 0)], None, 1, 2, F_INDOOR, (230, 235, 245)),
    ('sink', 'Sink', 1, 1, 0.9, 120, 'Bathroom', 0, 'WASH', [(0, 1)], None, 0, 0, F_INDOOR, (220, 225, 235)),
    ('jacuzzi', 'Jacuzzi', 2, 2, 0.6, 2400, 'Bathroom', 3, 'HOTTUB', [(0, 2)], None, 2, 4, F_INDOOR, (120, 200, 230)),
    ('reception_desk', 'Reception desk', 3, 1, 1.1, 1200, 'Lobby', 0, 'CHECKIN', [(1, 1)], (1, -1), 2, 2, F_INDOOR | F_STATION, (190, 140, 90)),
    ('key_rack', 'Key rack', 1, 1, 2.0, 150, 'Lobby', 0, 'KEYS', [], None, 0, 1, F_INDOOR | F_TALL, (120, 80, 40)),
    ('concierge_desk', 'Concierge desk', 2, 1, 1.1, 1500, 'Lobby', 3, 'CONCIERGE', [(0, 1)], (0, -1), 1, 3, F_INDOOR | F_STATION, (150, 60, 80)),
    ('waiting_sofa', 'Lobby sofa', 2, 1, 0.8, 500, 'Lobby', 0, 'SIT', [(0, 1), (1, 1)], None, 0, 2, F_INDOOR, (90, 140, 120)),
    ('coffee_table', 'Coffee table', 1, 1, 0.5, 120, 'Lobby', 0, 'NONE', [], None, 0, 1, F_INDOOR, (150, 110, 70)),
    ('plant', 'Potted plant', 1, 1, 1.4, 60, 'Decor', 0, 'NONE', [], None, 0, 2, IO | F_TALL, (60, 160, 70)),
    ('luggage_cart', 'Luggage cart', 1, 1, 1.3, 250, 'Lobby', 1, 'NONE', [], None, 0, 1, F_INDOOR, (230, 190, 70)),
    ('table_2', 'Table for two', 1, 1, 0.8, 200, 'Dining', 0, 'EAT', [(-1, 0), (1, 0)], None, 1, 1, IO, (200, 170, 130)),
    ('table_4', 'Table for four', 2, 2, 0.8, 380, 'Dining', 0, 'EAT', [(-1, 0), (2, 1), (0, 2), (1, -1)], None, 2, 2, IO, (190, 160, 120)),
    ('buffet', 'Buffet counter', 3, 1, 1.0, 1400, 'Dining', 2, 'EAT', [(0, 1), (1, 1), (2, 1)], None, 2, 3, F_INDOOR, (220, 200, 160)),
    ('bar_counter', 'Bar counter', 1, 1, 1.1, 300, 'Dining', 1, 'DRINK', [(0, 1)], (0, -1), 3, 1, IO | F_STATION | F_JOIN, (120, 70, 50)),
    ('bar_stool', 'Bar stool', 1, 1, 0.8, 70, 'Dining', 1, 'DRINK', [(0, 0)], None, 1, 0, IO, (200, 50, 60)),
    ('bar_shelf', 'Bottle shelf', 2, 1, 2.0, 600, 'Dining', 1, 'NONE', [], None, 0, 3, F_INDOOR | F_TALL, (160, 110, 60)),
    ('lounge_chair', 'Armchair', 1, 1, 0.9, 220, 'Decor', 1, 'SIT', [(0, 1)], None, 0, 2, F_INDOOR, (170, 80, 120)),
    ('piano', 'Grand piano', 2, 2, 1.1, 4000, 'Leisure', 3, 'MUSIC', [(0, 2)], None, 3, 5, F_INDOOR, (30, 30, 36)),
    ('jukebox', 'Jukebox', 1, 1, 1.6, 900, 'Leisure', 1, 'MUSIC', [(0, 1)], None, 5, 2, F_INDOOR | F_NOISY_NIGHT | F_TALL, (230, 120, 60)),
    ('stove', 'Stove', 1, 1, 1.0, 900, 'Dining', 0, 'COOK', [], (0, 1), 3, 0, F_INDOOR | F_STATION, (200, 205, 215)),
    ('prep_counter', 'Kitchen pass', 2, 1, 1.0, 500, 'Dining', 0, 'PASS', [(0, 1), (1, 1)], (0, -1), 1, 0, F_INDOOR, (210, 215, 225)),
    ('fridge', 'Fridge', 1, 1, 2.0, 700, 'Dining', 0, 'FRIDGE', [(0, 1)], None, 1, 0, F_INDOOR | F_TALL, (235, 240, 245)),
    ('dishwasher', 'Dishwasher', 1, 1, 0.9, 600, 'Dining', 1, 'NONE', [(0, 1)], None, 2, 0, F_INDOOR, (190, 195, 205)),
    ('kitchen_sink', 'Kitchen sink', 1, 1, 0.9, 250, 'Dining', 0, 'NONE', [(0, 1)], None, 1, 0, F_INDOOR, (200, 210, 220)),
    ('washer', 'Washing machine', 1, 1, 1.0, 800, 'Service', 0, 'LAUNDRY', [(0, 1)], None, 3, 0, F_INDOOR, (240, 240, 245)),
    ('dryer', 'Tumble dryer', 1, 1, 1.0, 700, 'Service', 1, 'DRY', [(0, 1)], None, 2, 0, F_INDOOR, (230, 230, 240)),
    ('folding_table', 'Folding table', 2, 1, 0.8, 200, 'Service', 1, 'NONE', [(0, 1)], None, 0, 0, F_INDOOR, (200, 190, 170)),
    ('linen_shelf', 'Linen shelf', 1, 1, 1.8, 180, 'Service', 0, 'LINEN', [(0, 1)], None, 0, 0, F_INDOOR | F_TALL, (180, 200, 230)),
    ('storage_shelf', 'Storage shelf', 1, 1, 1.8, 150, 'Service', 0, 'STORE', [(0, 1)], None, 0, 0, F_INDOOR | F_TALL, (170, 150, 120)),
    ('locker', 'Staff lockers', 1, 1, 2.0, 200, 'Service', 0, 'LOCKER', [(0, 1)], None, 0, 0, F_INDOOR | F_TALL, (120, 140, 170)),
    ('staff_table', 'Staff table', 2, 2, 0.8, 300, 'Service', 0, 'REST', [(-1, 0), (2, 1)], None, 0, 1, F_INDOOR, (170, 150, 120)),
    ('vending', 'Vending machine', 1, 1, 2.0, 650, 'Service', 0, 'SNACK', [(0, 1)], None, 1, 1, F_INDOOR | F_TALL, (210, 60, 70)),
    ('cot', 'Staff cot', 1, 2, 0.5, 150, 'Service', 1, 'REST', [(1, 0)], None, 0, 0, F_INDOOR, (120, 140, 110)),
    ('massage_bed', 'Massage bed', 1, 2, 0.8, 1600, 'Leisure', 3, 'MASSAGE', [(1, 0)], (-1, 1), 0, 3, F_INDOOR | F_STATION, (240, 230, 220)),
    ('sauna', 'Sauna', 3, 3, 2.4, 6000, 'Leisure', 3, 'SAUNA', [(1, 3)], None, 0, 4, F_INDOOR | F_TALL, (180, 120, 70)),
    ('hot_tub', 'Hot tub', 2, 2, 0.6, 3000, 'Leisure', 2, 'HOTTUB', [(0, 2), (1, 2)], None, 2, 4, IO, (110, 200, 220)),
    ('towel_rack', 'Towel rack', 1, 1, 1.2, 90, 'Leisure', 2, 'NONE', [], None, 0, 1, IO, (240, 240, 240)),
    ('treadmill', 'Treadmill', 1, 2, 1.2, 1800, 'Leisure', 2, 'GYM', [(0, 2)], None, 3, 1, F_INDOOR, (70, 70, 80)),
    ('weights', 'Weight bench', 2, 1, 0.8, 900, 'Leisure', 2, 'GYM', [(0, 1)], None, 3, 1, F_INDOOR, (90, 90, 110)),
    ('lounger', 'Sun lounger', 1, 2, 0.5, 250, 'Leisure', 1, 'LOUNGE', [(1, 0)], None, 1, 1, IO, (240, 240, 230)),
    ('umbrella', 'Parasol', 1, 1, 2.2, 180, 'Leisure', 1, 'NONE', [], None, 0, 2, IO | F_TALL, (240, 120, 100)),
    ('conf_table', 'Conference table', 3, 2, 0.8, 2200, 'Leisure', 2, 'MEET', [(-1, 0), (-1, 1), (3, 0), (3, 1), (1, 2)], None, 1, 2, F_INDOOR, (120, 80, 50)),
    ('projector', 'Projector screen', 1, 1, 2.0, 1200, 'Leisure', 2, 'NONE', [], None, 0, 1, F_INDOOR | F_TALL, (230, 230, 235)),
    ('lectern', 'Lectern', 1, 1, 1.2, 300, 'Leisure', 2, 'NONE', [(0, 1)], None, 0, 1, F_INDOOR, (130, 90, 50)),
    ('stairs', 'Stairs', 2, 4, 3.0, 2500, 'Build', 0, 'NONE', [(0, 4), (1, 4)], None, 1, 0, F_INDOOR | F_TRANSPORT, (180, 170, 160)),
    ('elevator', 'Elevator', 2, 2, 3.0, 8000, 'Build', 0, 'NONE', [(0, 2), (1, 2)], None, 1, 1, F_INDOOR | F_TRANSPORT | F_TALL, (170, 180, 200)),
    ('glass_elevator', 'Glass elevator', 2, 2, 3.0, 18000, 'Build', 3, 'NONE', [(0, 2), (1, 2)], None, 1, 6, F_INDOOR | F_TRANSPORT | F_TALL, (170, 230, 250)),
    ('grand_staircase', 'Grand staircase', 3, 6, 3.0, 15000, 'Build', 3, 'NONE', [(0, 6), (1, 6), (2, 6)], None, 1, 8, F_INDOOR | F_TRANSPORT, (220, 200, 160)),
    ('chandelier', 'Chandelier', 2, 2, 2.0, 7000, 'Decor', 3, 'NONE', [], None, 0, 6, F_INDOOR | F_VOID, (255, 230, 140)),
    ('skylight', 'Skylight', 2, 2, 0.3, 5000, 'Decor', 3, 'NONE', [], None, 0, 6, F_INDOOR | F_VOID | F_ROOFTOP, (190, 230, 255)),
    ('indoor_tree', 'Indoor tree', 2, 2, 5.5, 4000, 'Decor', 3, 'NONE', [], None, 0, 6, F_INDOOR | F_ATRIUM | F_TALL, (60, 150, 70)),
    ('fountain', 'Fountain', 2, 2, 1.2, 5000, 'Decor', 3, 'NONE', [], None, 2, 6, IO | F_ATRIUM, (150, 200, 230)),
    ('door', 'Door', 1, 1, 2.2, 150, 'Build', 0, 'NONE', [], None, 0, 0, F_WALLPIECE, (150, 100, 60)),
    ('window', 'Window', 1, 1, 2.2, 200, 'Build', 0, 'NONE', [], None, 0, 1, F_WALLPIECE, (170, 220, 250)),
    ('railing', 'Railing', 1, 1, 1.0, 0, 'Build', 0, 'NONE', [], None, 0, 0, F_WALLPIECE, (200, 200, 210)),
    ('railing_glass', 'Glass railing', 1, 1, 1.0, 0, 'Build', 0, 'NONE', [], None, 0, 1, F_WALLPIECE, (190, 230, 250)),
    ('bed_king', 'King-size bed', 2, 2, 0.7, 1800, 'Bedroom', 3, 'SLEEP', [(0, 2), (1, 2)], None, 0, 4, F_INDOOR, (180, 80, 110)),
    ('phone', 'Phone table', 1, 1, 0.7, 120, 'Bedroom', 0, 'PHONE', [(0, 1)], None, 0, 1, F_INDOOR, (230, 210, 170)),
    ('modem', 'Dial-up modem', 1, 1, 0.8, 300, 'Bedroom', 0, 'MODEM', [(0, 1)], None, 1, 1, F_INDOOR, (210, 205, 185)),
    ('arcade', 'Arcade cabinet', 1, 1, 1.8, 1100, 'Leisure', 1, 'PLAY', [(0, 1)], None, 4, 2, F_INDOOR | F_TALL, (80, 60, 160)),
    ('palm', 'Palm tree', 1, 1, 3.0, 150, 'Decor', 0, 'NONE', [], None, 0, 2, F_OUTDOOR | F_TALL, (70, 170, 80)),
    ('coffee_machine', 'Coffee machine', 1, 1, 1.0, 400, 'Service', 0, 'COFFEE', [(0, 1)], None, 1, 1, F_INDOOR, (120, 70, 50)),
]
assert len(OBJ) == 74
OK = {o[0]: i for i, o in enumerate(OBJ)}

# floors / room surfaces offered by the Rooms tab
FLOORS = [   # key, name, kind (0 room, 1 corridor, 2 service corridor, 3 outdoor deck, 4 pool water), price/tile, colour
    ('carpet_red', 'Room: red carpet', 0, 30, (170, 60, 70)),
    ('carpet_blue', 'Room: blue carpet', 0, 30, (60, 80, 160)),
    ('carpet_green', 'Room: green carpet', 0, 30, (60, 120, 90)),
    ('wood', 'Room: wood floor', 0, 40, (170, 120, 70)),
    ('tile', 'Room: white tiles', 0, 35, (215, 220, 225)),
    ('marble', 'Room: marble', 0, 80, (235, 225, 210)),
    ('terracotta', 'Room: terracotta', 0, 35, (200, 110, 70)),
    ('concrete', 'Room: concrete', 0, 15, (150, 150, 150)),
    ('corr_carpet', 'Corridor: carpet', 1, 25, (150, 50, 60)),
    ('corr_marble', 'Corridor: marble', 1, 70, (225, 215, 200)),
    ('service', 'Service corridor', 2, 10, (130, 130, 120)),
    ('deck', 'Outdoor deck', 3, 25, (180, 140, 90)),
    ('pool_water', 'Pool water', 4, 120, (60, 170, 230)),
]
# floor surface (texture) per floor key, and ground terrain kinds
SURF = ['grass', 'sand', 'road', 'sidewalk', 'sea', 'carpet', 'carpet2', 'carpet3', 'wood', 'tile', 'marble',
        'terracotta', 'concrete', 'deck', 'pool_water', 'roof']

# room types: key, name, unlock, min tiles, requirements [(alternatives, count)], bonus objects, overlay colour, noise
ROOMS = [
    ('none', 'Empty room', 0, 0, [], [], (120, 120, 130), 0),
    ('corridor', 'Corridor', 0, 0, [], ['plant', 'floor_lamp', 'vending', 'lounge_chair'], (190, 180, 160), 0),
    ('service', 'Service corridor', 0, 0, [], [], (130, 130, 120), 0),
    ('outdoor', 'Garden & deck', 0, 0, [], ['palm', 'plant', 'umbrella', 'lounger', 'table_2'], (120, 190, 110), 0),
    ('guest', 'Guest room', 0, 6, [(['bed_single', 'bed_double'], 1), (['wardrobe'], 1), (['toilet'], 1), (['sink'], 1),
                                   (['shower', 'bathtub'], 1)],
     ['tv', 'desk', 'chair', 'nightstand', 'floor_lamp', 'plant', 'phone', 'modem', 'minibar', 'sofa', 'lounge_chair'],
     (90, 150, 230), 0),
    ('suite', 'Suite', 3, 12, [(['bed_king'], 1), (['wardrobe'], 1), (['toilet'], 1), (['sink'], 1),
                               (['bathtub', 'jacuzzi'], 1), (['sofa', 'lounge_chair'], 1), (['tv'], 1)],
     ['desk', 'minibar', 'phone', 'modem', 'floor_lamp', 'plant', 'nightstand', 'jacuzzi', 'piano', 'coffee_table'],
     (200, 110, 220), 0),
    ('lobby', 'Lobby', 0, 9, [(['reception_desk'], 1), (['key_rack'], 1)],
     ['waiting_sofa', 'plant', 'coffee_table', 'floor_lamp', 'piano', 'fountain', 'concierge_desk', 'luggage_cart',
      'indoor_tree', 'lounge_chair'], (240, 200, 90), 2),
    ('restaurant', 'Restaurant', 0, 8, [(['table_2', 'table_4'], 2)],
     ['plant', 'floor_lamp', 'piano', 'buffet', 'fountain', 'indoor_tree'], (240, 140, 80), 2),
    ('kitchen', 'Kitchen', 0, 6, [(['stove'], 1), (['fridge'], 1), (['prep_counter'], 1)],
     ['kitchen_sink', 'dishwasher', 'storage_shelf'], (230, 230, 240), 4),
    ('laundry', 'Laundry', 0, 4, [(['washer'], 1), (['linen_shelf'], 1)], ['dryer', 'folding_table'],
     (160, 210, 240), 4),
    ('storage', 'Storage', 0, 4, [(['storage_shelf'], 2)], [], (170, 150, 120), 0),
    ('staff', 'Staff room', 0, 4, [(['locker'], 1), (['staff_table', 'cot', 'coffee_machine'], 1)],
     ['vending', 'plant', 'coffee_machine', 'cot', 'staff_table'], (150, 170, 140), 1),
    ('bar', 'Bar', 1, 6, [(['bar_counter'], 1), (['bar_stool'], 2)],
     ['bar_shelf', 'jukebox', 'lounge_chair', 'piano', 'arcade', 'table_2', 'plant'], (220, 80, 120), 6),
    ('pool', 'Pool', 1, 10, [(['lounger'], 1)], ['umbrella', 'palm', 'towel_rack', 'plant', 'hot_tub'],
     (80, 210, 230), 3),
    ('spa', 'Spa', 3, 6, [(['massage_bed'], 1), (['sauna', 'hot_tub'], 1)], ['towel_rack', 'plant', 'floor_lamp'],
     (240, 170, 200), 0),
    ('gym', 'Gym', 2, 6, [(['treadmill'], 1), (['weights'], 1)], ['towel_rack', 'vending', 'plant'], (240, 120, 70), 3),
    ('conference', 'Conference room', 2, 9, [(['conf_table'], 1), (['projector'], 1)],
     ['lectern', 'coffee_machine', 'plant', 'floor_lamp'], (130, 120, 210), 1),
]
RK = {r[0]: i for i, r in enumerate(ROOMS)}

GUESTS = [   # key, name, unlock stars, budget per night, stays (nights), wants (room kind)
    ('business', 'Business traveller', 0, 110, 1),
    ('family', 'Family', 1, 140, 2),
    ('honeymoon', 'Honeymooners', 3, 320, 2),
    ('rockstar', 'Rock star', 4, 900, 1),
]
STAFF = [   # key, name, wage per day, uniform colour
    ('receptionist', 'Receptionist', 105, (200, 40, 60)),
    ('housekeeper', 'Housekeeper', 85, (90, 160, 220)),
    ('cook', 'Cook', 125, (240, 240, 240)),
    ('waiter', 'Waiter', 90, (40, 40, 50)),
    ('bartender', 'Bartender', 100, (120, 40, 120)),
    ('therapist', 'Spa therapist', 140, (240, 200, 220)),
    ('bellhop', 'Bellhop', 80, (200, 60, 50)),
    ('maintenance', 'Maintenance', 105, (60, 110, 60)),
    ('security', 'Security', 110, (30, 30, 50)),
]

# --- reviews: (key, text) ; the game picks lines by what went right or wrong
REVIEWS = [
    ('no_reception', '"Nobody at the front desk. I rang the bell for 20 minutes."'),
    ('no_room', '"No vacancy?! In THIS economy?"'),
    ('too_pricey', '"That price? I\'m not made of dot-com stock."'),
    ('dirty', '"Found someone else\'s sock in my bed. Gross."'),
    ('noisy', '"Couldn\'t sleep - the bar was thumping till 3am."'),
    ('hungry', '"Waited forever for room service. Ate the mints."'),
    ('no_food', '"No restaurant. Had to drive to the Burger Barn."'),
    ('no_fun', '"Nothing to do here but watch the ceiling fan."'),
    ('slow', '"The elevator took longer than my 56k modem."'),
    ('broken', '"The shower was broken. The TV was broken. I was broken."'),
    ('no_wifi', '"No dial-up in the room?! How do I check my Hotmail?"'),
    ('no_pool', '"The kids wanted a pool. The kids got sad."'),
    ('no_spa', '"A honeymoon without a spa? Unromantic."'),
    ('no_suite', '"I asked for a suite. Do you know who I AM?"'),
    ('great_room', '"Comfy bed, fluffy towels. Would book again!"'),
    ('great_food', '"The chef is a genius. Five stars for the soup."'),
    ('great_view', '"That atrium! I felt like I was in a music video."'),
    ('great_pool', '"Pool, sun, sea. The kids are finally quiet."'),
    ('great_bar', '"Best mojitos this side of the millennium."'),
    ('great_service', '"Bellhop carried my bags AND my emotional baggage."'),
    ('great_spa', '"The massage melted me into a puddle. Bliss."'),
    ('great_wifi', '"Dial-up in every room. Checked my email twice!"'),
    ('rock_trash', '"Trashed the room. Best gig ever. Will return."'),
    ('ok', '"It was fine. Nice enough. A hotel, for sure."'),
    ('lost', '"Got lost looking for my room. Twice."'),
    ('tired', '"The staff looked exhausted. Hire more people!"'),
]

# --- the economy: every price, cost and rate the simulation balances with (gen_sim.akr ECO_*).
# Tuned (2026-10-01, polish workstream C) so that the demo hotel a new player gets makes a modest
# profit (about 10-20% of takings) with reviews around 3.5 stars, and a well-run hotel grows.
ECONOMY = [
    # takings
    ('MEAL', 22, 'a meal in the restaurant (or at a bar table)'),
    ('ROOM_SERVICE', 32, 'a meal brought to the room (phone)'),
    ('DRINK', 12, 'a drink at the bar'),
    ('MASSAGE', 85, 'a massage'),
    ('HOTTUB', 20, 'the hot tub or sauna'),
    ('MEETING', 60, 'a conference meeting'),
    ('SNACK', 3, 'a vending-machine snack'),
    ('MINIBAR', 9, 'the minibar'),
    # costs
    ('UPKEEP_OBJ', 3, 'upkeep per object per day'),
    ('UPKEEP_TILES', 4, 'upkeep: one dollar a day per this many room tiles'),
    ('CRATE_COST', 56, 'a crate of food from the delivery van (8 meals)'),
    ('LINEN_COST', 25, 'fresh linen bought when there is no laundry'),
    ('LOAN_RATE', 6, 'loan interest, percent a year'),
    # supplies
    ('CRATE_MEALS', 8, 'meals in a crate (into the fridge)'),
    ('FRIDGE_MAX', 16, 'meals a fridge holds'),
    ('SHELF_CRATES', 6, 'crates a storage shelf holds'),
    ('DELIVERY_H1', 7, 'the delivery van comes at this hour'),
    ('DELIVERY_H2', 15, '... and again at this one'),
    # guests
    ('MOOD0', 16, 'a new guest\'s mood'),
    ('REVIEW_BASE', 32, 'review score (x10) before mood: stars = (base + mood / 3 + 5) / 10'),
    ('ARRIVALS', 1, 'guests an hour, plus one per star and per 25 reputation'),
    ('CHECKIN_H0', 12, 'guests arrive from this hour (rooms are cleaned after the 10:00 check-outs)'),
    ('CHECKIN_H1', 22, '... until this one'),
    ('RUSH_H0', 15, 'twice as many arrive from this hour'),
    ('RUSH_H1', 19, '... until this one'),
]


def write_gen_sim(path):
    """Writes the ECONOMY table as `const ECO_<NAME> = value` (generated: never edit by hand)."""
    lines = ['// Generated by tools/checkin_data.py (the ECONOMY table): do not edit by hand.']
    for key, value, what in ECONOMY:
        lines.append('const ECO_%s = %d%s// %s' % (key, value, ' ' * max(1, 22 - len(key) - len(str(value))), what))
    open(path, 'w').write('\n'.join(lines) + '\n')


if __name__ == '__main__':
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(here, '..', 'carts', 'checkin', 'gen_sim.akr')
    write_gen_sim(out)
    print('wrote', os.path.normpath(out))
