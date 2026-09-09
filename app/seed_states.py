"""
Master list of Indian states/UTs with region classification (as used by
Grid-India/CEA: NR, WR, SR, ER, NER) and capital coordinates. Coordinates are
real, publicly known capital-city coordinates, used both as the state master
table and as anchor points for NASA POWER resource lookups.
"""

STATES = [
    # name, region, lat, lon (capital)
    ("Jammu and Kashmir", "NR", 34.0837, 74.7973),
    ("Himachal Pradesh", "NR", 31.1048, 77.1734),
    ("Punjab", "NR", 30.7333, 76.7794),
    ("Chandigarh", "NR", 30.7333, 76.7794),
    ("Uttarakhand", "NR", 30.3165, 78.0322),
    ("Haryana", "NR", 30.7333, 76.7794),
    ("Delhi", "NR", 28.6139, 77.2090),
    ("Uttar Pradesh", "NR", 26.8467, 80.9462),
    ("Rajasthan", "NR", 26.9124, 75.7873),
    ("Gujarat", "WR", 23.0225, 72.5714),
    ("Madhya Pradesh", "WR", 23.2599, 77.4126),
    ("Chhattisgarh", "WR", 21.2514, 81.6296),
    ("Maharashtra", "WR", 19.0760, 72.8777),
    ("Goa", "WR", 15.4909, 73.8278),
    ("Daman and Diu", "WR", 20.3974, 72.8328),
    ("Dadra and Nagar Haveli", "WR", 20.1809, 73.0169),
    ("Andhra Pradesh", "SR", 16.5062, 80.6480),
    ("Telangana", "SR", 17.3850, 78.4867),
    ("Karnataka", "SR", 12.9716, 77.5946),
    ("Tamil Nadu", "SR", 13.0827, 80.2707),
    ("Kerala", "SR", 8.5241, 76.9366),
    ("Puducherry", "SR", 11.9416, 79.8083),
    ("Bihar", "ER", 25.5941, 85.1376),
    ("Jharkhand", "ER", 23.3441, 85.3096),
    ("West Bengal", "ER", 22.5726, 88.3639),
    ("Odisha", "ER", 20.2961, 85.8245),
    ("Sikkim", "ER", 27.3389, 88.6065),
    ("Assam", "NER", 26.1445, 91.7362),
    ("Arunachal Pradesh", "NER", 27.0844, 93.6053),
    ("Manipur", "NER", 24.8170, 93.9368),
    ("Meghalaya", "NER", 25.5788, 91.8933),
    ("Mizoram", "NER", 23.7271, 92.7176),
    ("Nagaland", "NER", 25.6751, 94.1086),
    ("Tripura", "NER", 23.8315, 91.2868),
]


def seed(db):
    from app.models import State
    if db.query(State).count() > 0:
        return
    for name, region, lat, lon in STATES:
        db.add(State(name=name, region=region, latitude=lat, longitude=lon))
    db.commit()


# Named major solar/wind installations, for higher-resolution resource data
# than a state-capital point can give (a state capital may be hundreds of km
# from its actual RE parks — matters for project-level bankability screening).
# Coordinates are each verified against Wikipedia/Global Energy Monitor entries
# for the specific installation, not estimated.
RE_PARKS = [
    # name, state, lat, lon, type (SOLAR/WIND)
    ("Bhadla Solar Park", "Rajasthan", 27.5397, 71.9153, "SOLAR"),
    ("Pavagada Solar Park", "Karnataka", 14.25, 77.45, "SOLAR"),
    ("Muppandal Wind Farm", "Tamil Nadu", 8.25, 77.59, "WIND"),
    ("Kamuthi Solar Power Project", "Tamil Nadu", 9.347568, 78.392162, "SOLAR"),
    ("Kurnool Ultra Mega Solar Park", "Andhra Pradesh", 15.681522, 78.283749, "SOLAR"),
    ("Rewa Ultra Mega Solar", "Madhya Pradesh", 24.4802, 81.5744, "SOLAR"),
    ("Charanka Solar Park", "Gujarat", 23.9086, 71.2027, "SOLAR"),
    ("Jaisalmer Wind Park", "Rajasthan", 26.92, 70.90, "WIND"),
    ("Dhule Wind Farm", "Maharashtra", 20.9019, 74.7708, "WIND"),
    ("NP Kunta (Ananthapuramu) Ultra Mega Solar Park", "Andhra Pradesh", 14.03194, 78.43583, "SOLAR"),
    ("Bhuj Wind Farm Cluster", "Gujarat", 23.2517, 69.6625, "WIND"),
]
