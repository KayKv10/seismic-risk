"""Annual aircraft movements for global airports (approximate, thousands).

An aircraft movement is one landing or one takeoff.  Counts include both
commercial and cargo operations, making this metric more representative of
overall aviation activity than passenger numbers alone.

Sources: FAA ATADS (US airports), Eurocontrol STATFOR (Europe),
ACI World Traffic Report, airport authority annual reports.
Used for HTML visualization marker sizing only — not for risk scoring.

Update periodically from the sources above.
"""

# IATA code -> approximate annual aircraft movements (thousands)
AIRPORT_MOVEMENTS: dict[str, float] = {
    # North America
    "ATL": 900.0,   # Atlanta Hartsfield-Jackson
    "DFW": 680.0,   # Dallas/Fort Worth
    "DEN": 600.0,   # Denver
    "ORD": 860.0,   # Chicago O'Hare
    "LAX": 650.0,   # Los Angeles
    "JFK": 460.0,   # New York JFK
    "EWR": 450.0,   # Newark Liberty
    "SFO": 450.0,   # San Francisco
    "SEA": 430.0,   # Seattle-Tacoma
    "LAS": 480.0,   # Las Vegas McCarran
    "MCO": 400.0,   # Orlando
    "CLT": 540.0,   # Charlotte
    "PHX": 420.0,   # Phoenix Sky Harbor
    "MIA": 420.0,   # Miami
    "IAH": 410.0,   # Houston George Bush
    "BOS": 380.0,   # Boston Logan
    "MSP": 360.0,   # Minneapolis-St Paul
    "FLL": 280.0,   # Fort Lauderdale
    "DTW": 350.0,   # Detroit Metro
    "PHL": 300.0,   # Philadelphia
    "BWI": 250.0,   # Baltimore/Washington
    "IAD": 240.0,   # Washington Dulles
    "DCA": 280.0,   # Washington Reagan
    "SLC": 320.0,   # Salt Lake City
    "SAN": 220.0,   # San Diego
    "TPA": 220.0,   # Tampa
    "PDX": 200.0,   # Portland OR
    "STL": 150.0,   # St Louis
    "HNL": 260.0,   # Honolulu
    "AUS": 180.0,   # Austin
    "BNA": 220.0,   # Nashville
    "RDU": 140.0,   # Raleigh-Durham
    "MCI": 120.0,   # Kansas City
    "SMF": 130.0,   # Sacramento
    "SJC": 150.0,   # San Jose
    "CLE": 110.0,   # Cleveland
    "IND": 140.0,   # Indianapolis
    "PIT": 120.0,   # Pittsburgh
    "CMH": 100.0,   # Columbus OH
    "MKE": 90.0,    # Milwaukee
    "OAK": 170.0,   # Oakland
    "MEM": 340.0,   # Memphis (FedEx global hub)
    "SDF": 260.0,   # Louisville (UPS Worldport)
    "ANC": 280.0,   # Anchorage (cargo refuel hub)
    "CVG": 210.0,   # Cincinnati/N. Kentucky (DHL Americas)
    "RFD": 40.0,    # Rockford (UPS/Amazon Air)
    "ONT": 80.0,    # Ontario CA (cargo)
    "YYZ": 460.0,   # Toronto Pearson
    "YVR": 300.0,   # Vancouver
    "YUL": 230.0,   # Montreal Trudeau
    "MEX": 410.0,   # Mexico City
    "CUN": 220.0,   # Cancun
    "GDL": 130.0,   # Guadalajara
    "GRU": 260.0,   # Sao Paulo Guarulhos
    "GIG": 110.0,   # Rio de Janeiro Galeao
    "CGH": 200.0,   # Sao Paulo Congonhas
    "BSB": 120.0,   # Brasilia
    "BOG": 280.0,   # Bogota El Dorado
    "SCL": 180.0,   # Santiago Chile
    "LIM": 190.0,   # Lima Jorge Chavez
    "EZE": 100.0,   # Buenos Aires Ezeiza
    "PTY": 120.0,   # Panama City Tocumen
    "UIO": 55.0,    # Quito
    # Europe
    "LHR": 480.0,   # London Heathrow
    "CDG": 490.0,   # Paris Charles de Gaulle
    "IST": 520.0,   # Istanbul
    "AMS": 500.0,   # Amsterdam Schiphol
    "MAD": 420.0,   # Madrid Barajas
    "FRA": 460.0,   # Frankfurt
    "BCN": 350.0,   # Barcelona El Prat
    "LGW": 280.0,   # London Gatwick
    "MUC": 380.0,   # Munich
    "FCO": 300.0,   # Rome Fiumicino
    "ORY": 220.0,   # Paris Orly
    "SVO": 280.0,   # Moscow Sheremetyevo
    "ZRH": 260.0,   # Zurich
    "CPH": 250.0,   # Copenhagen
    "OSL": 230.0,   # Oslo Gardermoen
    "DUB": 230.0,   # Dublin
    "PMI": 200.0,   # Palma de Mallorca
    "VIE": 250.0,   # Vienna
    "MAN": 200.0,   # Manchester UK
    "ARN": 200.0,   # Stockholm Arlanda
    "LIS": 220.0,   # Lisbon
    "BRU": 220.0,   # Brussels
    "ATH": 200.0,   # Athens
    "HEL": 180.0,   # Helsinki
    "WAW": 160.0,   # Warsaw Chopin
    "PRG": 140.0,   # Prague
    "BUD": 120.0,   # Budapest
    "EDI": 120.0,   # Edinburgh
    "STN": 180.0,   # London Stansted
    "HAM": 150.0,   # Hamburg
    "AYT": 200.0,   # Antalya
    "SAW": 200.0,   # Istanbul Sabiha Gokcen
    "LEJ": 75.0,    # Leipzig/Halle (DHL European hub)
    "CGN": 110.0,   # Cologne/Bonn (UPS/FedEx Europe)
    "EMA": 60.0,    # East Midlands (DHL/UPS UK)
    "LGG": 45.0,    # Liege (cargo hub)
    # Middle East
    "DXB": 410.0,   # Dubai
    "DOH": 250.0,   # Doha Hamad
    "AUH": 180.0,   # Abu Dhabi
    "JED": 260.0,   # Jeddah
    "RUH": 200.0,   # Riyadh
    "TLV": 180.0,   # Tel Aviv Ben Gurion
    "AMM": 70.0,    # Amman Queen Alia
    "BAH": 80.0,    # Bahrain
    "MCT": 60.0,    # Muscat
    "KWI": 110.0,   # Kuwait
    # Africa
    "JNB": 210.0,   # Johannesburg OR Tambo
    "CPT": 100.0,   # Cape Town
    "CAI": 180.0,   # Cairo
    "CMN": 80.0,    # Casablanca Mohammed V
    "ADD": 120.0,   # Addis Ababa Bole
    "NBO": 70.0,    # Nairobi Jomo Kenyatta
    "LOS": 60.0,    # Lagos Murtala Muhammed
    "ALG": 55.0,    # Algiers
    "TUN": 45.0,    # Tunis Carthage
    "DSS": 25.0,    # Dakar Blaise Diagne
    # South & Central Asia
    "DEL": 520.0,   # Delhi Indira Gandhi
    "BOM": 330.0,   # Mumbai Chhatrapati Shivaji
    "BLR": 270.0,   # Bangalore Kempegowda
    "MAA": 180.0,   # Chennai
    "HYD": 200.0,   # Hyderabad Rajiv Gandhi
    "CCU": 150.0,   # Kolkata Netaji Subhas
    "COK": 80.0,    # Kochi
    "GOI": 65.0,    # Goa Dabolim
    "CMB": 80.0,    # Colombo Bandaranaike
    "DAC": 100.0,   # Dhaka Hazrat Shahjalal
    "ISB": 70.0,    # Islamabad
    "KHI": 90.0,    # Karachi Jinnah
    "LHE": 55.0,    # Lahore
    "KTM": 60.0,    # Kathmandu Tribhuvan
    # East Asia
    "PEK": 600.0,   # Beijing Capital
    "PKX": 200.0,   # Beijing Daxing
    "PVG": 490.0,   # Shanghai Pudong
    "CAN": 470.0,   # Guangzhou Baiyun
    "CTU": 370.0,   # Chengdu Tianfu / Shuangliu
    "SZX": 350.0,   # Shenzhen Bao'an
    "KMG": 310.0,   # Kunming Changshui
    "SHA": 270.0,   # Shanghai Hongqiao
    "XIY": 290.0,   # Xi'an Xianyang
    "HGH": 260.0,   # Hangzhou Xiaoshan
    "CKG": 250.0,   # Chongqing Jiangbei
    "NKG": 200.0,   # Nanjing Lukou
    "WUH": 180.0,   # Wuhan Tianhe
    "HND": 480.0,   # Tokyo Haneda
    "NRT": 250.0,   # Tokyo Narita
    "KIX": 190.0,   # Osaka Kansai
    "ICN": 400.0,   # Seoul Incheon
    "GMP": 180.0,   # Seoul Gimpo
    "CJU": 200.0,   # Jeju
    "TPE": 260.0,   # Taipei Taoyuan
    "HKG": 300.0,   # Hong Kong
    "MFM": 60.0,    # Macau
    "ULN": 20.0,    # Ulaanbaatar Chinggis Khaan
    # Southeast Asia
    "SIN": 380.0,   # Singapore Changi
    "BKK": 370.0,   # Bangkok Suvarnabhumi
    "DMK": 200.0,   # Bangkok Don Mueang
    "KUL": 330.0,   # Kuala Lumpur
    "CGK": 370.0,   # Jakarta Soekarno-Hatta
    "MNL": 310.0,   # Manila Ninoy Aquino
    "SGN": 270.0,   # Ho Chi Minh City Tan Son Nhat
    "HAN": 200.0,   # Hanoi Noi Bai
    "DPS": 160.0,   # Bali Ngurah Rai
    "CEB": 100.0,   # Cebu Mactan
    "RGN": 50.0,    # Yangon
    "PNH": 50.0,    # Phnom Penh
    "REP": 25.0,    # Siem Reap
    # Oceania
    "SYD": 340.0,   # Sydney Kingsford Smith
    "MEL": 280.0,   # Melbourne Tullamarine
    "BNE": 210.0,   # Brisbane
    "PER": 120.0,   # Perth
    "AKL": 170.0,   # Auckland
    "CHC": 60.0,    # Christchurch
    "WLG": 50.0,    # Wellington
    "NAN": 25.0,    # Nadi Fiji
    # Russia & Central Asia
    "DME": 200.0,   # Moscow Domodedovo
    "LED": 150.0,   # St Petersburg Pulkovo
    "VVO": 30.0,    # Vladivostok
    "ALA": 55.0,    # Almaty
    "NQZ": 35.0,    # Astana Nursultan Nazarbayev
    "TAS": 40.0,    # Tashkent
}

DEFAULT_MOVEMENTS: float = 10.0
"""Fallback for airports not in the lookup (thousands).

Ensures all airports get a minimum marker size in the visualization.
"""
