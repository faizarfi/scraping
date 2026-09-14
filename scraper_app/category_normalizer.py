import re

# Daftar kata tombol UI / aksi navigasi Google Maps yang BUKAN kategori
UI_ACTION_TERMS = {
    'rute', 'directions', 'direction', 'situs web', 'website',
    'simpan', 'save', 'saved', 'bagikan', 'share',
    'telepon', 'call', 'pesan', 'message', 'ringkasan', 'overview',
    'tentang', 'about', 'nearby', 'di sekitar', 'mulai', 'start',
    'foto', 'photo', 'photos', 'menu', 'ulasan', 'review', 'reviews'
}

# Daftar Plus Code atau kode lokasi tanpa vokal
def is_plus_code_or_code(text):
    if not text:
        return False
    t = text.strip()
    # Pola Plus Code Google Maps (misal 'CVCW+RC8' atau '93M3+Q7J' atau 'CVCWRC8')
    if re.match(r'^[2-9A-Z]{4,8}\+?[2-9A-Z]{2,4}$', t, re.I):
        return True
    # Jika alfanumerik kapital >= 5 karakter tanpa huruf vokal (seperti 'CVCWRC8')
    if len(t) >= 5 and re.match(r'^[A-Z0-9]+$', t):
        if not any(v in t.lower() for v in ['a', 'i', 'u', 'e', 'o']):
            return True
    return False


CATEGORY_MAPPING_RULES = [
    # 1. Laundry & Binatu
    (r'\b(binatu|laundry|cucian|mesin cuci|dry clean|kiloan)\b', 'Laundry & Binatu'),

    # 2. Hotel & Penginapan
    (r'\b(hotel|homestay|guest house|hostel|resor|resort|penginapan|vila|villa|motel|inn)\b', 'Hotel & Penginapan'),

    # 3. Kafe & Kedai Kopi
    (r'\b(kopi|kafe|cafe|espresso|kedai teh|teh)\b', 'Kafe & Kedai Kopi'),

    # 4. Restoran & Rumah Makan
    (r'\b(restoran|rumah makan|warung|warteg|padang|bakso|soto|sate|ayam penyet|ayam goreng|seblak|pujasera|prasmanan|mie|nasi|brunch|salad|steak|pizza|dapur umum)\b', 'Restoran & Rumah Makan'),

    # 5. Bengkel & Otomotif
    (r'\b(bengkel|otomotif|ganti oli|ketok magic|bubut|spooring|ban motor|ban mobil|servis motor|servis mobil|suku cadang|aksesori mobil|perbaikan bodi)\b', 'Bengkel & Otomotif'),

    # 6. Salon & Barber Shop (kecuali salon hewan)
    (r'\b(cukur|barber|salon rambut|penata rambut|barbershop)\b', 'Salon & Barber Shop'),

    # 7. Apotek & Toko Obat
    (r'\b(apotek|obat|farmasi)\b', 'Apotek & Toko Obat'),

    # 8. Kantor Notaris & PPAT
    (r'\b(notaris|ppat)\b', 'Kantor Notaris & PPAT'),

    # 9. Ekspedisi & Logistik
    (r'\b(ekspedisi|logistik|kurir|pengiriman|kargo|truk ekspedisi)\b', 'Ekspedisi & Logistik'),

    # 10. SPBU & Pangkalan Gas LPG
    (r'\b(gas|elpiji|lpg|spbu|bensin|pertamina|solar|tabung gas)\b', 'SPBU & Pangkalan Gas LPG'),

    # 11. Toko Bangunan & Material
    (r'\b(bahan bangunan|material|semen|tegel|keramik|genteng)\b', 'Toko Bangunan & Material'),

    # 12. Jasa Konstruksi & Kontraktor
    (r'\b(konstruksi|kontraktor|arsitek|pembangunan perumahan)\b', 'Jasa Konstruksi & Kontraktor'),

    # 13. Konveksi & Pakaian
    (r'\b(konveksi|pakaian|baju|jahit|tailor|sablon|kaos custom)\b', 'Konveksi & Pakaian'),

    # 14. Pendidikan & Kursus
    (r'\b(les|kursus|bimbingan|sekolah|pendidikan|belajar|kampus|universitas|perguruan tinggi|smk|akademi)\b', 'Tempat Kursus & Bimbingan Belajar'),

    # 15. Kesehatan & Medis
    (r'\b(puskesmas|klinik|dokter|kesehatan|rumah sakit|laboratorium|medis)\b', 'Puskesmas & Klinik Kesehatan'),

    # 16. Toko Buah & Sayur Segar
    (r'\b(buah|sayur|sayuran)\b', 'Toko Buah & Sayur Segar'),

    # 17. Fotografer & Studio Foto
    (r'\b(foto|photo|fotografer|fotografi)\b', 'Fotografer & Studio Foto'),

    # 18. Pet Shop & Perawatan Hewan
    (r'\b(hewan|pet shop|kucing|anjing|pakan hewan)\b', 'Pet Shop & Perawatan Hewan'),

    # 19. Penyedia Layanan Internet & Komputer
    (r'\b(internet|komputer|warnet|wifi|networking)\b', 'Penyedia Layanan Internet & Komputer'),

    # 20. Spesialis Logam & Bengkel Las
    (r'\b(las|logam|besi)\b', 'Spesialis Logam & Bengkel Las'),

    # 21. Rental Kendaraan (Mobil & Motor)
    (r'\b(rental|sewa mobil|sewa motor)\b', 'Rental Kendaraan (Mobil & Motor)'),

    # 22. Pariwisata & Rekreasi
    (r'\b(wisata|rekreasi|taman hiburan|tujuan wisata|kolam renang|museum)\b', 'Pariwisata & Rekreasi'),

    # 23. Showroom Jual Beli Kendaraan Bekas
    (r'\b(dealer mobil|dealer motor|kendaraan bekas|mobil bekas|motor bekas)\b', 'Showroom Jual Beli Kendaraan Bekas'),

    # 24. Percetakan & Fotokopi
    (r'\b(fotokopi|percetakan|cetak digital|stempel|printer digital)\b', 'Percetakan & Fotokopi'),

    # 25. UMKM & Bisnis Lokal
    (r'\b(umkm|ksp|koperasi|kerajinan)\b', 'UMKM & Bisnis Lokal'),

    # 26. Toko & Retail Umum
    (r'\b(swalayan|minimarket|supermarket|kelontong|pasar|toserba)\b', 'Retail & Toko Swalayan'),
]


def extract_category_from_query(query_text):
    """
    Ekstrak kategori dari teks query pencarian (misal: 'Laundry Kiloan di Kabupaten Karanganyar' -> 'Laundry Kiloan')
    """
    if not query_text:
        return ""
    clean_q = re.split(r'\s+di\s+|\s+in\s+|,', query_text.strip(), flags=re.IGNORECASE)[0].strip()
    return clean_q


def is_anomalous_category(cat):
    """
    Cek apakah suatu string kategori adalah anomali tombol UI, Plus Code, review, atau simbol
    """
    if not cat or not cat.strip():
        return True
    t = cat.strip().lower()
    if t in UI_ACTION_TERMS:
        return True
    if is_plus_code_or_code(cat.strip()):
        return True
    if any(phrase in t for phrase in ['tidak ada ulasan', 'belum ada ulasan', 'no reviews', 'bintang']):
        return True
    if any(0xE000 <= ord(c) <= 0xF8FF for c in cat):
        return True
    if t in ['·', '•', '-', '.', 'bisnis', 'tempat', 'rute', 'situs web']:
        return True
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")) or '?' in t:
        return False
    return False


def normalize_category(raw_category, search_query=""):
    """
    Normalkan kategori mentah ke kategori standar yang rapi dan terunifikasi:
    1. Jika raw_category adalah anomali (Rute, Situs Web, Plus Code, Tidak ada ulasan),
       pulihkan dari search_query.
    2. Cocokkan dengan pola aturan pemetaan untuk menyatukan variasi sinonim (Binatu -> Laundry & Binatu).
    3. Jika tidak cocok pola manapun, kembalikan kategori mentah yang sudah dibersihkan secara rapi (Title Case).
    """
    cat = (raw_category or "").strip()

    # Jika anomali, pulihkan dari search_query
    if is_anomalous_category(cat):
        extracted = extract_category_from_query(search_query)
        if extracted and not is_anomalous_category(extracted):
            cat = extracted
        else:
            cat = "Bisnis"

    # Jalankan pencocokan aturan normalisasi
    cat_lower = cat.lower()
    for pattern, standard_name in CATEGORY_MAPPING_RULES:
        if re.search(pattern, cat_lower, re.IGNORECASE):
            return standard_name

    # Cek apakah query pencarian memiliki kategori standar yang lebih relevan
    if search_query:
        sq_extracted = extract_category_from_query(search_query).lower()
        for pattern, standard_name in CATEGORY_MAPPING_RULES:
            if re.search(pattern, sq_extracted, re.IGNORECASE):
                return standard_name

    # Kembalikan kategori asli yang diformat rapi
    clean_title = cat.strip().title()
    return clean_title if clean_title else "Bisnis"
