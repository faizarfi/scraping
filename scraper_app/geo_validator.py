import json
import os
import re
import math

# Prioritaskan file GeoJSON resmi pemerintah 2025 yang disediakan di root proyek
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIMARY_GEOJSON = os.path.join(WORKSPACE_DIR, 'peta_kab_202513313.geojson')
FALLBACK_BOUNDARY = os.path.join(os.path.dirname(__file__), 'data', 'karanganyar_boundary.json')

_COLOMADU_RING = None
_MAIN_RING = None
_BBOX_PART1 = None  # Colomadu bbox
_BBOX_PART2 = None  # Main Karanganyar bbox
_IS_LOADED = False


def _load_boundary():
    global _COLOMADU_RING, _MAIN_RING, _BBOX_PART1, _BBOX_PART2, _IS_LOADED
    if _IS_LOADED:
        return
    _IS_LOADED = True

    target_file = PRIMARY_GEOJSON if os.path.exists(PRIMARY_GEOJSON) else FALLBACK_BOUNDARY
    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if 'features' in data and data['features']:
            raw_coords = data['features'][0].get('geometry', {}).get('coordinates', [])
        elif 'coordinates' in data:
            raw_coords = data['coordinates']
        else:
            raw_coords = []

        for part in raw_coords:
            outer = part[0]
            lons = [p[0] for p in outer]
            lats = [p[1] for p in outer]
            bbox = (min(lats) - 0.001, max(lats) + 0.001, min(lons) - 0.001, max(lons) + 0.001)

            # Colomadu merupakan eksklave di sebelah barat bujur 110.803 BT
            if max(lons) < 110.803:
                _COLOMADU_RING = outer
                _BBOX_PART1 = bbox
            else:
                _MAIN_RING = outer
                _BBOX_PART2 = bbox

    except Exception as e:
        print(f"Warning: gagal membaca data batas {target_file}: {e}")


def point_in_polygon(x, y, ring):
    """
    Ray-casting algorithm untuk menentukan titik (x=lon, y=lat) berada dalam polygon
    """
    n = len(ring)
    inside = False
    p1x, p1y = ring[0]
    for i in range(1, n + 1):
        p2x, p2y = ring[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def check_coordinates_part(lat, lon, tolerance=0.001):
    """
    Cek posisi koordinat terhadap batas resmi Kabupaten Karanganyar:
    Return:
        1: Di dalam Part 1 (Kecamatan Colomadu)
        2: Di dalam Part 2 (16 Kecamatan Karanganyar lainnya)
        0: Di luar Kabupaten Karanganyar
    """
    if lat is None or lon is None:
        return 0

    # Filter titik default Indonesia yang anomali (-2.44, 117.88, dll)
    if not (-8.5 <= lat <= -6.5 and 109.5 <= lon <= 112.5):
        return 0

    _load_boundary()

    # 1. Cek Part 1 (Colomadu)
    if _BBOX_PART1 and _COLOMADU_RING:
        min_lat, max_lat, min_lon, max_lon = _BBOX_PART1
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            if point_in_polygon(lon, lat, _COLOMADU_RING):
                return 1
            if tolerance > 0:
                for dlat in (-tolerance, 0, tolerance):
                    for dlon in (-tolerance, 0, tolerance):
                        if point_in_polygon(lon + dlon, lat + dlat, _COLOMADU_RING):
                            return 1

    # 2. Cek Part 2 (Utama Karanganyar)
    if _BBOX_PART2 and _MAIN_RING:
        min_lat, max_lat, min_lon, max_lon = _BBOX_PART2
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            if point_in_polygon(lon, lat, _MAIN_RING):
                return 2
            if tolerance > 0:
                for dlat in (-tolerance, 0, tolerance):
                    for dlon in (-tolerance, 0, tolerance):
                        if point_in_polygon(lon + dlon, lat + dlat, _MAIN_RING):
                            return 2

    return 0

# 17 Kecamatan resmi di Kabupaten Karanganyar beserta titik pusat (centroid)
DISTRICT_CENTROIDS = {
    'Colomadu': (-7.5324, 110.7487),
    'Gondangrejo': (-7.4680, 110.8072),
    'Kebakkramat': (-7.5311, 110.9010),
    'Kerjo': (-7.5366, 111.0627),
    'Jenawi': (-7.5749, 111.1346),
    'Mojogedang': (-7.5717, 111.0228),
    'Jaten': (-7.5776, 110.8956),
    'Tasikmadu': (-7.5798, 110.9307),
    'Karanganyar': (-7.5976, 110.9500),
    'Karangpandan': (-7.6149, 111.0769),
    'Ngargoyoso': (-7.5853, 111.1044),
    'Matesih': (-7.6465, 111.0480),
    'Jumantono': (-7.6545, 110.9954),
    'Tawangmangu': (-7.6679, 111.1194),
    'Jumapolo': (-7.7040, 111.0079),
    'Jatiyoso': (-7.7297, 111.0860),
    'Jatipuro': (-7.7521, 111.0182),
}

# Daftar desa/kelurahan resmi per kecamatan di Kabupaten Karanganyar
DISTRICT_VILLAGES = {
    'Colomadu': [
        'baturan', 'klodran', 'gedongan', 'tohudan', 'blulukan', 
        'gawanan', 'gajahan', 'paulan', 'malangjiwan', 'bolon', 'ngasem'
    ],
    'Gondangrejo': [
        'bulurejo', 'dayu', 'jatikuwung', 'jeruksawit', 'karangturi', 
        'kragan', 'krendowahono', 'plesungan', 'rejosari', 'selokaton', 
        'tuban', 'wonorejo', 'wonosari'
    ],
    'Jaten': [
        'brujul', 'dagen', 'jaten', 'jati', 'ngringo', 'sroyo', 'suruhkalang'
    ],
    'Jatipuro': [
        'jatimulyo', 'jatipuro', 'jatiroyo', 'jatisobo', 'jatisuko', 
        'mandungan', 'ngepungsari'
    ],
    'Jatiyoso': [
        'beruk', 'jatisawit', 'jatiyoso', 'karangsari', 'petung', 
        'tlobo', 'wonokeling', 'wonorejo'
    ],
    'Jenawi': [
        'anggrasmanis', 'balong', 'gumeng', 'jenawi', 'lempong', 
        'menjing', 'seloromo', 'sidomukti', 'trengguli'
    ],
    'Jumantono': [
        'blorong', 'gemantar', 'genengan', 'ngunut', 'sambirejo', 
        'sedayu', 'sringin', 'sukosari', 'tunggulrejo', 'tugu'
    ],
    'Jumapolo': [
        'bakalan', 'giriwondo', 'jatirejo', 'jumantoro', 'jumapolo', 
        'kadipiro', 'karangbangun', 'kedawung', 'kwangsan', 'lemahbang', 
        'paseban', 'ploso'
    ],
    'Karanganyar': [
        'bejen', 'bolong', 'cangakan', 'delingan', 'gega', 'gayamprit', 
        'jantiharjo', 'jungke', 'lalung', 'popongan', 'tegalgede'
    ],
    'Karangpandan': [
        'bangsri', 'dayu', 'doplang', 'gerdu', 'harjosari', 'karang', 
        'karangpandan', 'ngemplak', 'salam', 'tohkuning'
    ],
    'Kebakkramat': [
        'alastuwo', 'banjarharjo', 'kaliwuluh', 'kebak', 'kemiri', 
        'macanan', 'malanggaten', 'nangsri', 'pulosari', 'waru'
    ],
    'Kerjo': [
        'botok', 'ganten', 'karangrejo', 'kuto', 'kwadungan', 
        'plosorejo', 'sumberejo', 'tamansari', 'tawangsari'
    ],
    'Matesih': [
        'dawung', 'gantiwarno', 'giriloyo', 'karangbangun', 'koripan', 
        'matesih', 'ngadiluwih', 'pablengan', 'plosorejo'
    ],
    'Mojogedang': [
        'bangle', 'gebyok', 'gentungan', 'kaliboto', 'kedungjeruk', 
        'mojogedang', 'mojoroto', 'munggur', 'ngadirejo', 'pendem', 
        'pereng', 'pojok'
    ],
    'Ngargoyoso': [
        'berjo', 'dukuh', 'girimulyo', 'jatirejo', 'kemuning', 
        'ngargoyoso', 'nglegok', 'pantenan', 'segorogunung'
    ],
    'Tasikmadu': [
        'buran', 'gaum', 'kalijirak', 'kaling', 'karangmojo', 
        'kragilan', 'ngijo', 'pandeyan', 'papahan', 'suruh'
    ],
    'Tawangmangu': [
        'bandardawung', 'blumbang', 'gondosuli', 'kalisoro', 'karanglo', 
        'nglebak', 'plumbon', 'tawangmangu', 'tengklik'
    ]
}

# Kota/Kabupaten tetangga dan kata kunci yang PASTI di luar Karanganyar
OUTSIDE_REGIONS = [
    # Kota Surakarta / Solo
    'surakarta', 'kota solo', 'kota surakarta', 'banjarsari', 'laweyan', 
    'pasar kliwon', 'serengan', 'jebres', 'manahan', 'purwosari', 
    'sriwedari', 'kerten', 'nusukan', 'gilingan', 'mojosongo', 'pucangsawit',
    'semanggi', 'baluwarti', 'timuran', 'keprabon', 'ketelan',
    # Sukoharjo
    'sukoharjo', 'kabupaten sukoharjo', 'kartasura', 'solo baru', 'grogol', 
    'baki', 'bendosari', 'mojolaban', 'polokarto', 'tawangsari',
    # Boyolali
    'boyolali', 'kabupaten boyolali', 'banyudono', 'sawit', 'sambi',
    # Sragen
    'sragen', 'kabupaten sragen', 'kalijambe', 'masaran', 'gemolong',
    # Wonogiri & Klaten
    'wonogiri', 'selogiri', 'klaten', 'delanggu', 'ceper',
    # Kota lain
    'semarang', 'yogyakarta', 'jogja', 'sleman', 'bantul', 'kulon progo',
    'surabaya', 'malang', 'jakarta', 'bandung', 'magetan', 'ngawi'
]

# Kode pos yang PASTI di luar Karanganyar
# Karanganyar: Colomadu (57171-57179), Gondangrejo (57188), Kebakkramat (57282 / 577xx), sisanya (577xx)
NON_KARANGANYAR_POSTAL_REGEX = re.compile(
    r'\b(5711[0-9]|5712[0-9]|5713[0-9]|5714[0-9]|5715[0-9]|5716[0-9]|573[0-9]{2}|574[0-9]{2}|575[0-9]{2}|576[0-9]{2}|50[0-9]{3}|55[0-9]{3}|60[0-9]{3}|1[0-9]{4}|40[0-9]{3})\b'
)





def has_outside_keywords(text):
    """
    Deteksi apakah alamat/teks secara eksplisit merujuk ke kota/kabupaten lain di luar Karanganyar
    """
    if not text:
        return False
    t = text.lower()

    # Cek kode pos non-Karanganyar
    if NON_KARANGANYAR_POSTAL_REGEX.search(t):
        return True

    for reg in OUTSIDE_REGIONS:
        # Pastikan kecocokan sebagai kata utuh atau frasa
        pattern = r'(?:\b|\bjl\.\s*|\bkota\s+)' + re.escape(reg) + r'\b'
        if re.search(pattern, t):
            # Pengecualian: nama tempat bisnis yang mencantumkan nama kota pemasaran
            # misalnya "Bean27 Autodetailing Solo, Jl. Gedongan, Colomadu"
            # Jika memuat 'colomadu' atau 'karanganyar', jangan langsung tolak
            if 'colomadu' in t or 'karanganyar' in t:
                # Tapi tolak jika format alamatnya "Kota Surakarta" atau "Kabupaten Sukoharjo"
                if re.search(r'\b(?:kota surakarta|kabupaten sukoharjo|kabupaten boyolali|kabupaten sragen)\b', t):
                    return True
                continue
            return True
    return False


def is_valid_karanganyar_place(lat, lng, address="", name="", target_district=None):
    """
    Fungsi penentu utama apakah suatu tempat valid dan benar-benar berada di Karanganyar.
    Mendukung filter target_district (misal 'Colomadu').
    """
    # 1. Jika koordinat tersedia: koordinat adalah penentu kebenaran fisik tertinggi (Ground Truth)
    if lat is not None and lng is not None:
        part = check_coordinates_part(lat, lng)
        if part == 0:
            # Koordinat di luar batas Karanganyar (misal di Solo, Kartasura, Boyolali, atau Kalimantan)
            return False

        if target_district and target_district.strip():
            target_clean = target_district.strip().lower()
            if target_clean == 'colomadu':
                # Tempat harus berada di Part 1 (Colomadu)
                return part == 1
            else:
                # Jika targetnya kecamatan lain di Karanganyar (misal Jaten), tempat harus di Part 2
                return part == 2

        # Jika user memilih "Semua Kecamatan (Karanganyar)"
        return part in (1, 2)

    # 2. Fallback jika koordinat tidak terbaca (null): periksa teks alamat & nama
    combined = f"{address or ''} {name or ''}".lower()
    if has_outside_keywords(combined):
        return False

    # Cek apakah memuat kata kunci Karanganyar atau salah satu kecamatan Karanganyar
    if 'karanganyar' in combined or 'colomadu' in combined:
        return True

    for d in DISTRICT_CENTROIDS.keys():
        if d.lower() in combined:
            return True

    for d_name, v_list in DISTRICT_VILLAGES.items():
        if any(v in combined for v in v_list):
            return True

    # Jika koordinat tidak ada dan alamat tidak memuat nama daerah Karanganyar sama sekali
    return False


def resolve_karanganyar_district(lat, lon, address="", query="", target_district=""):
    """
    Deteksi nama kecamatan resmi (1 dari 17 kecamatan di Karanganyar) secara akurat
    berdasarkan posisi geolokasi (poligon) dan pencocokan teks nama desa/kecamatan.
    """
    addr_lower = (address or "").lower()

    # 1. Cek koordinat geofencing
    part = check_coordinates_part(lat, lon)
    if part == 1:
        return 'Colomadu'

    if part == 2 and lat is not None and lon is not None:
        # Cek apakah alamat memuat nama kecamatan spesifik di Part 2
        for d in DISTRICT_CENTROIDS.keys():
            if d == 'Colomadu':
                continue
            if re.search(r'\b' + re.escape(d.lower()) + r'\b', addr_lower):
                return d

        # Cek apakah alamat memuat nama desa/kelurahan Karanganyar di Part 2
        for d, v_list in DISTRICT_VILLAGES.items():
            if d == 'Colomadu':
                continue
            for v in v_list:
                if re.search(r'\b' + re.escape(v) + r'\b', addr_lower):
                    return d

        # Tentukan kecamatan terdekat berdasarkan jarak centroid di Part 2
        best_d = 'Karanganyar'
        best_dist = float('inf')
        for d, (clat, clon) in DISTRICT_CENTROIDS.items():
            if d == 'Colomadu':
                continue
            dist = (lat - clat)**2 + (lon - clon)**2
            if dist < best_dist:
                best_dist = dist
                best_d = d
        return best_d

    # 2. Fallback jika koordinat tidak ada: cek teks alamat
    m = re.search(r'Kec(?:amatan|\.)\s+([A-Za-z0-9\s]+?)(?:,|$|\.|\d|\-)', address or '', re.IGNORECASE)
    if m:
        extracted = m.group(1).strip().title()
        for d in DISTRICT_CENTROIDS.keys():
            if d.lower() == extracted.lower():
                return d

    for d in DISTRICT_CENTROIDS.keys():
        if re.search(r'\b' + re.escape(d.lower()) + r'\b', addr_lower):
            return d

    for d, v_list in DISTRICT_VILLAGES.items():
        for v in v_list:
            if re.search(r'\b' + re.escape(v) + r'\b', addr_lower):
                return d

    # 3. Fallback target_district jika valid di Karanganyar
    if target_district and target_district.strip():
        td_clean = target_district.strip().title()
        for d in DISTRICT_CENTROIDS.keys():
            if d.lower() == td_clean.lower():
                return d

    return 'Karanganyar'
