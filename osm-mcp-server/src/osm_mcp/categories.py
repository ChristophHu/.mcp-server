CATEGORIES = {
    "restaurant": ("amenity", "restaurant"), "cafe": ("amenity", "cafe"), "bar": ("amenity", "bar"),
    "pub": ("amenity", "pub"), "fast_food": ("amenity", "fast_food"), "ice_cream": ("amenity", "ice_cream"),
    "hotel": ("tourism", "hotel"), "hostel": ("tourism", "hostel"), "guest_house": ("tourism", "guest_house"),
    "apartment": ("tourism", "apartment"), "camp_site": ("tourism", "camp_site"), "museum": ("tourism", "museum"),
    "attraction": ("tourism", "attraction"), "gallery": ("tourism", "gallery"), "viewpoint": ("tourism", "viewpoint"),
    "information": ("tourism", "information"), "artwork": ("tourism", "artwork"), "castle": ("historic", "castle"),
    "monument": ("historic", "monument"), "ruins": ("historic", "ruins"),
    "supermarket": ("shop", "supermarket"), "bakery": ("shop", "bakery"), "convenience": ("shop", "convenience"),
    "pharmacy": ("amenity", "pharmacy"), "hospital": ("amenity", "hospital"), "doctors": ("amenity", "doctors"),
    "police": ("amenity", "police"), "atm": ("amenity", "atm"), "bank": ("amenity", "bank"), "fuel": ("amenity", "fuel"),
    "charging_station": ("amenity", "charging_station"), "parking": ("amenity", "parking"), "toilets": ("amenity", "toilets"),
    "drinking_water": ("amenity", "drinking_water"), "bus_stop": ("highway", "bus_stop"),
    "train_station": ("railway", "station"), "tram_stop": ("railway", "tram_stop"),
    "ferry_terminal": ("amenity", "ferry_terminal"), "bicycle_rental": ("amenity", "bicycle_rental"),
    "car_rental": ("amenity", "car_rental"), "playground": ("leisure", "playground"),
    "park": ("leisure", "park"), "beach": ("natural", "beach"), "swimming_pool": ("leisure", "swimming_pool"),
}


def resolve_category(value):
    if value in CATEGORIES:
        return CATEGORIES[value]
    parts = value.split("=")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_:-")
    if len(parts) > 2 or not parts[0] or any(not part or any(c not in allowed for c in part) for part in parts):
        raise ValueError('invalid tag filter: use "key" or "key=value" with letters, digits, underscore, colon and hyphen only')
    return (parts[0], parts[1] if len(parts) == 2 else None)
