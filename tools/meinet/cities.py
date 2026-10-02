"""US cities for the map labels (docs/BROADCAST.md, "Cities"): a general list of about 220
places, the large ones and enough smaller ones that every part of the country has a few.

Each entry is (name as broadcast, state, latitude, longitude, population): the city proper's
population, rounded, from the 2020 census. Nothing here is anyone's home city: that only ever
comes from the gateway's own config file.
"""

CITIES = [
    # Northeast
    ("New York", "NY", 40.71, -74.01, 8804000),
    ("Philadelphia", "PA", 39.95, -75.17, 1604000),
    ("Boston", "MA", 42.36, -71.06, 676000),
    ("Washington", "DC", 38.91, -77.04, 690000),
    ("Baltimore", "MD", 39.29, -76.61, 586000),
    ("Pittsburgh", "PA", 40.44, -80.00, 303000),
    ("Buffalo", "NY", 42.89, -78.88, 278000),
    ("Rochester", "NY", 43.16, -77.61, 211000),
    ("Binghamton", "NY", 42.10, -75.91, 48000),
    ("Providence", "RI", 41.82, -71.41, 191000),
    ("Syracuse", "NY", 43.05, -76.15, 149000),
    ("Hartford", "CT", 41.76, -72.68, 121000),
    ("Albany", "NY", 42.65, -73.76, 99000),
    ("Erie", "PA", 42.13, -80.09, 95000),
    ("Scranton", "PA", 41.41, -75.66, 76000),
    ("Portland", "ME", 43.66, -70.26, 68000),
    ("Harrisburg", "PA", 40.27, -76.88, 50000),
    ("Burlington", "VT", 44.48, -73.21, 45000),
    ("Bangor", "ME", 44.80, -68.77, 32000),
    ("State College", "PA", 40.79, -77.86, 41000),
    ("Presque Isle", "ME", 46.68, -68.02, 9000),
    # Southeast
    ("Jacksonville", "FL", 30.33, -81.66, 950000),
    ("Charlotte", "NC", 35.23, -80.84, 875000),
    ("Nashville", "TN", 36.16, -86.78, 689000),
    ("Memphis", "TN", 35.15, -90.05, 633000),
    ("Louisville", "KY", 38.25, -85.76, 633000),
    ("Atlanta", "GA", 33.75, -84.39, 499000),
    ("Raleigh", "NC", 35.78, -78.64, 468000),
    ("Virginia Beach", "VA", 36.85, -75.98, 459000),
    ("Miami", "FL", 25.76, -80.19, 442000),
    ("Tampa", "FL", 27.95, -82.46, 385000),
    ("Lexington", "KY", 38.04, -84.50, 323000),
    ("Orlando", "FL", 28.54, -81.38, 308000),
    ("Greensboro", "NC", 36.07, -79.79, 299000),
    ("Richmond", "VA", 37.54, -77.44, 227000),
    ("Huntsville", "AL", 34.73, -86.59, 215000),
    ("Columbus", "GA", 32.46, -84.99, 207000),
    ("Macon", "GA", 32.84, -83.63, 157000),
    ("Asheville", "NC", 35.60, -82.55, 95000),
    ("Augusta", "GA", 33.47, -81.97, 202000),
    ("Birmingham", "AL", 33.52, -86.80, 201000),
    ("Montgomery", "AL", 32.37, -86.30, 201000),
    ("Tallahassee", "FL", 30.44, -84.28, 196000),
    ("Knoxville", "TN", 35.96, -83.92, 191000),
    ("Mobile", "AL", 30.69, -88.04, 187000),
    ("Chattanooga", "TN", 35.05, -85.31, 181000),
    ("Jackson", "MS", 32.30, -90.18, 154000),
    ("Charleston", "SC", 32.78, -79.93, 150000),
    ("Savannah", "GA", 32.08, -81.09, 148000),
    ("Columbia", "SC", 34.00, -81.03, 137000),
    ("Wilmington", "NC", 34.23, -77.94, 115000),
    ("Roanoke", "VA", 37.27, -79.94, 100000),
    ("Fort Myers", "FL", 26.64, -81.87, 86000),
    ("Greenville", "SC", 34.85, -82.40, 71000),
    ("Charleston", "WV", 38.35, -81.63, 49000),
    ("Tupelo", "MS", 34.26, -88.70, 38000),
    ("Key West", "FL", 24.56, -81.78, 26000),
    # Midwest
    ("Chicago", "IL", 41.88, -87.63, 2746000),
    ("Columbus", "OH", 39.96, -83.00, 906000),
    ("Indianapolis", "IN", 39.77, -86.16, 888000),
    ("Detroit", "MI", 42.33, -83.05, 639000),
    ("Milwaukee", "WI", 43.04, -87.91, 577000),
    ("Kansas City", "MO", 39.10, -94.58, 508000),
    ("Omaha", "NE", 41.26, -95.93, 486000),
    ("St. Paul", "MN", 44.95, -93.09, 312000),
    ("Wichita", "KS", 37.69, -97.34, 398000),
    ("Cleveland", "OH", 41.50, -81.69, 373000),
    ("Cincinnati", "OH", 39.10, -84.51, 309000),
    ("St. Louis", "MO", 38.63, -90.20, 302000),
    ("Lincoln", "NE", 40.81, -96.70, 291000),
    ("Toledo", "OH", 41.65, -83.54, 271000),
    ("Madison", "WI", 43.07, -89.40, 270000),
    ("Fort Wayne", "IN", 41.08, -85.14, 264000),
    ("Des Moines", "IA", 41.59, -93.62, 214000),
    ("Grand Rapids", "MI", 42.96, -85.67, 199000),
    ("Sioux Falls", "SD", 43.55, -96.73, 193000),
    ("Springfield", "MO", 37.21, -93.29, 169000),
    ("Salina", "KS", 38.84, -97.61, 47000),
    ("Joplin", "MO", 37.08, -94.51, 52000),
    ("St. Joseph", "MO", 39.77, -94.85, 72000),
    ("Rochester", "MN", 44.02, -92.47, 121000),
    ("Lansing", "MI", 42.73, -84.56, 113000),
    ("Dayton", "OH", 39.76, -84.19, 138000),
    ("Davenport", "IA", 41.52, -90.58, 102000),
    ("Champaign", "IL", 40.12, -88.24, 88000),
    ("St. Cloud", "MN", 45.56, -94.16, 68000),
    ("Cedar Rapids", "IA", 41.98, -91.67, 138000),
    ("Topeka", "KS", 39.05, -95.68, 127000),
    ("Columbia", "MO", 38.95, -92.33, 126000),
    ("Fargo", "ND", 46.88, -96.79, 126000),
    ("Evansville", "IN", 37.97, -87.57, 117000),
    ("Springfield", "IL", 39.80, -89.65, 114000),
    ("Peoria", "IL", 40.69, -89.59, 113000),
    ("Green Bay", "WI", 44.51, -88.02, 107000),
    ("Duluth", "MN", 46.79, -92.10, 87000),
    ("Sioux City", "IA", 42.50, -96.40, 86000),
    ("Rapid City", "SD", 44.08, -103.23, 75000),
    ("Bismarck", "ND", 46.81, -100.78, 74000),
    ("Grand Forks", "ND", 47.93, -97.03, 59000),
    ("Grand Island", "NE", 40.93, -98.34, 53000),
    ("Minot", "ND", 48.23, -101.30, 48000),
    ("Jefferson City", "MO", 38.58, -92.17, 43000),
    ("Dodge City", "KS", 37.75, -100.02, 28000),
    ("Hays", "KS", 38.88, -99.33, 21000),
    ("North Platte", "NE", 41.12, -100.77, 23000),
    ("Aberdeen", "SD", 45.46, -98.49, 28000),
    ("Traverse City", "MI", 44.76, -85.62, 16000),
    ("Marquette", "MI", 46.54, -87.40, 21000),
    ("Alpena", "MI", 45.06, -83.43, 10000),
    ("Bemidji", "MN", 47.47, -94.88, 15000),
    ("Int'l Falls", "MN", 48.60, -93.41, 6000),
    ("Pierre", "SD", 44.37, -100.35, 14000),
    ("Cape Girardeau", "MO", 37.31, -89.52, 40000),
    ("Mason City", "IA", 43.15, -93.20, 27000),
    # South
    ("Houston", "TX", 29.76, -95.37, 2305000),
    ("San Antonio", "TX", 29.42, -98.49, 1435000),
    ("Dallas", "TX", 32.78, -96.80, 1304000),
    ("Austin", "TX", 30.27, -97.74, 962000),
    ("Fort Worth", "TX", 32.76, -97.33, 919000),
    ("Oklahoma City", "OK", 35.47, -97.52, 681000),
    ("El Paso", "TX", 31.76, -106.49, 679000),
    ("Tulsa", "OK", 36.15, -95.99, 413000),
    ("New Orleans", "LA", 29.95, -90.07, 384000),
    ("Corpus Christi", "TX", 27.80, -97.40, 318000),
    ("Lubbock", "TX", 33.58, -101.86, 257000),
    ("Laredo", "TX", 27.51, -99.51, 255000),
    ("Baton Rouge", "LA", 30.45, -91.19, 227000),
    ("Little Rock", "AR", 34.75, -92.29, 203000),
    ("Amarillo", "TX", 35.22, -101.83, 200000),
    ("Shreveport", "LA", 32.53, -93.75, 188000),
    ("Brownsville", "TX", 25.90, -97.50, 187000),
    ("Midland", "TX", 32.00, -102.08, 133000),
    ("Abilene", "TX", 32.45, -99.73, 125000),
    ("Lafayette", "LA", 30.22, -92.02, 121000),
    ("Tyler", "TX", 32.35, -95.30, 106000),
    ("Wichita Falls", "TX", 33.91, -98.49, 102000),
    ("Waco", "TX", 31.55, -97.15, 138000),
    ("Fort Smith", "AR", 35.39, -94.40, 89000),
    ("San Angelo", "TX", 31.46, -100.44, 100000),
    ("Fayetteville", "AR", 36.06, -94.16, 94000),
    ("Monroe", "LA", 32.51, -92.12, 48000),
    ("Del Rio", "TX", 29.36, -100.90, 35000),
    ("Alpine", "TX", 30.36, -103.66, 6000),
    ("Guymon", "OK", 36.68, -101.48, 12000),
    # Mountain
    ("Denver", "CO", 39.74, -104.99, 716000),
    ("Colorado Springs", "CO", 38.83, -104.82, 479000),
    ("Pueblo", "CO", 38.25, -104.61, 112000),
    ("Pocatello", "ID", 42.86, -112.45, 56000),
    ("Boise", "ID", 43.62, -116.20, 236000),
    ("Salt Lake City", "UT", 40.76, -111.89, 200000),
    ("Billings", "MT", 45.78, -108.50, 117000),
    ("St. George", "UT", 37.10, -113.58, 95000),
    ("Missoula", "MT", 46.87, -113.99, 73000),
    ("Grand Junction", "CO", 39.06, -108.55, 66000),
    ("Cheyenne", "WY", 41.14, -104.82, 65000),
    ("Idaho Falls", "ID", 43.49, -112.03, 65000),
    ("Great Falls", "MT", 47.50, -111.30, 60000),
    ("Casper", "WY", 42.87, -106.31, 59000),
    ("Bozeman", "MT", 45.68, -111.04, 53000),
    ("Twin Falls", "ID", 42.56, -114.46, 52000),
    ("Gillette", "WY", 44.29, -105.50, 33000),
    ("Helena", "MT", 46.59, -112.04, 32000),
    ("Williston", "ND", 48.15, -103.62, 29000),
    ("Kalispell", "MT", 48.20, -114.31, 25000),
    ("Rock Springs", "WY", 41.59, -109.20, 24000),
    ("Elko", "NV", 40.83, -115.76, 21000),
    ("Durango", "CO", 37.28, -107.88, 19000),
    ("Riverton", "WY", 43.02, -108.38, 11000),
    ("Miles City", "MT", 46.41, -105.84, 8000),
    ("Havre", "MT", 48.55, -109.68, 10000),
    ("Alamosa", "CO", 37.47, -105.87, 10000),
    # Southwest
    ("Phoenix", "AZ", 33.45, -112.07, 1608000),
    ("Las Vegas", "NV", 36.17, -115.14, 642000),
    ("Las Cruces", "NM", 32.32, -106.76, 111000),
    ("Prescott", "AZ", 34.54, -112.47, 46000),
    ("Albuquerque", "NM", 35.08, -106.65, 565000),
    ("Tucson", "AZ", 32.22, -110.97, 543000),
    ("Yuma", "AZ", 32.69, -114.62, 96000),
    ("Santa Fe", "NM", 35.69, -105.94, 88000),
    ("Flagstaff", "AZ", 35.20, -111.65, 77000),
    ("Lake Havasu City", "AZ", 34.48, -114.32, 57000),
    ("Roswell", "NM", 33.39, -104.52, 48000),
    ("Farmington", "NM", 36.73, -108.21, 47000),
    ("Clovis", "NM", 34.40, -103.21, 39000),
    ("Gallup", "NM", 35.53, -108.74, 22000),
    ("Show Low", "AZ", 34.25, -110.03, 11000),
    ("Page", "AZ", 36.91, -111.46, 7000),
    ("Silver City", "NM", 32.77, -108.28, 10000),
    ("Ely", "NV", 39.25, -114.89, 4000),
    # West
    ("Los Angeles", "CA", 34.05, -118.24, 3899000),
    ("San Diego", "CA", 32.72, -117.16, 1387000),
    ("San Jose", "CA", 37.34, -121.89, 1013000),
    ("San Francisco", "CA", 37.77, -122.42, 874000),
    ("Fresno", "CA", 36.74, -119.79, 542000),
    ("Sacramento", "CA", 38.58, -121.49, 525000),
    ("Bakersfield", "CA", 35.37, -119.02, 403000),
    ("Visalia", "CA", 36.33, -119.29, 141000),
    ("Stockton", "CA", 37.96, -121.29, 321000),
    ("Riverside", "CA", 33.95, -117.40, 315000),
    ("Reno", "NV", 39.53, -119.81, 264000),
    ("Redding", "CA", 40.59, -122.39, 94000),
    ("Santa Barbara", "CA", 34.42, -119.70, 89000),
    ("San Luis Obispo", "CA", 35.28, -120.66, 47000),
    ("Eureka", "CA", 40.80, -124.16, 27000),
    ("Ukiah", "CA", 39.15, -123.21, 16000),
    ("Bishop", "CA", 37.36, -118.40, 4000),
    ("Winnemucca", "NV", 40.97, -117.74, 8000),
    # Pacific Northwest
    ("Seattle", "WA", 47.61, -122.33, 737000),
    ("Portland", "OR", 45.52, -122.68, 653000),
    ("Spokane", "WA", 47.66, -117.43, 229000),
    ("Kennewick", "WA", 46.21, -119.14, 84000),
    ("Klamath Falls", "OR", 42.22, -121.78, 22000),
    ("Eugene", "OR", 44.05, -123.09, 177000),
    ("Salem", "OR", 44.94, -123.04, 176000),
    ("Bend", "OR", 44.06, -121.31, 99000),
    ("Yakima", "WA", 46.60, -120.51, 97000),
    ("Medford", "OR", 42.33, -122.87, 86000),
    ("Lewiston", "ID", 46.42, -117.02, 34000),
    ("Pendleton", "OR", 45.67, -118.79, 17000),
    ("Burns", "OR", 43.59, -119.05, 3000),
    ("Omak", "WA", 48.41, -119.53, 5000),
]


def table():
    """The cities, largest first (ties in table order)."""
    out = [{"name": n, "state": s, "lat": lat, "lon": lon, "pop": p} for n, s, lat, lon, p in CITIES]
    out.sort(key=lambda c: -c["pop"])
    return out


# The map grid the spacing is measured on (docs/BROADCAST.md, "Map (kind 3)").
GRID_W, GRID_H = 64, 48
EDGE = 1.5                       # cells kept clear along the map's edges
SPACE_X, SPACE_Y = 10.0, 5.5     # no two cities closer than this (an ellipse, in cells)


def cell(box, lat, lon):
    """(x, y) of (lat, lon) on a box's 64 x 48 map grid, in cells from the top left."""
    s, n, w, e = box
    return (lon - w) / (e - w) * GRID_W, (n - lat) / (n - s) * GRID_H


def pick(box, seeds, cap, table_=None):
    """The cities for a map box, most prominent first: the seeds that fall inside (the home
    city, then the regions' cities), then the table largest first. A city too close on the map
    to one already chosen is skipped (seeds only need half the distance, so they are left out
    only where they would overlap); at most cap. Seeds and the result are dicts with name, lat,
    lon (and anything else they carry)."""
    chosen = []
    seeds = list(seeds)
    for k, c in enumerate(seeds + (table() if table_ is None else table_)):
        x, y = cell(box, c["lat"], c["lon"])
        if not (EDGE <= x <= GRID_W - EDGE and EDGE <= y <= GRID_H - EDGE):
            continue
        f = 0.5 if k < len(seeds) else 1.0
        near = False
        for d in chosen:
            dx, dy = cell(box, d["lat"], d["lon"])
            if ((x - dx) / (SPACE_X * f)) ** 2 + ((y - dy) / (SPACE_Y * f)) ** 2 < 1.0:
                near = True
                break
        if near:
            continue
        chosen.append(c)
        if len(chosen) >= cap:
            break
    return chosen
