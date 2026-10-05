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
    (r'\b(swalayan|supermarket|kelontong|pasar|toserba)\b', 'Retail & Toko Swalayan'),

    # 27. Masjid & Mushola
    (r'\b(masjid|mushola|musala|musholla|langgar|surau)\b', 'Masjid & Mushola'),

    # 28. Gereja & Tempat Ibadah
    (r'\b(gereja|kapel|chapel|vihara|pura|klenteng|tempat ibadah)\b', 'Gereja & Tempat Ibadah'),

    # 29. Bank & ATM
    (r'\b(bank|atm|bri|bca|mandiri|bni|btn|bsi|pegadaian)\b', 'Bank & ATM'),

    # 30. Minimarket & Toko Kelontong
    (r'\b(minimarket|indomaret|alfamart|alfamidi|lawson|circle k)\b', 'Minimarket & Toko Kelontong'),

    # 31. Toko Elektronik
    (r'\b(elektronik|elektrik|listrik|lampu|kabel)\b', 'Toko Elektronik'),

    # 32. Toko HP & Aksesoris
    (r'\b(handphone|hp|smartphone|gadget|aksesoris hp|casing|service hp)\b', 'Toko HP & Aksesoris'),

    # 33. Pabrik & Manufaktur
    (r'\b(pabrik|manufaktur|industri|pengolahan)\b', 'Pabrik & Manufaktur'),

    # 34. Gudang & Pergudangan
    (r'\b(gudang|pergudangan|warehouse|storage)\b', 'Gudang & Pergudangan'),

    # 35. Gym & Pusat Kebugaran
    (r'\b(gym|fitness|kebugaran|fitnes|pusat kebugaran|aerobik|yoga)\b', 'Gym & Pusat Kebugaran'),

    # 36. Dokter Gigi & Dental
    (r'\b(dokter gigi|dental|gigi|ortodonti)\b', 'Dokter Gigi & Dental'),

    # 37. Optik & Kacamata
    (r'\b(optik|kacamata|lensa|optical)\b', 'Optik & Kacamata'),

    # 38. Toko Kue & Bakery
    (r'\b(kue|bakery|roti|pastry|tart|cake|bakpao|donat)\b', 'Toko Kue & Bakery'),

    # 39. EO & Wedding Organizer
    (r'\b(wedding|pernikahan|event organizer|eo|dekorasi pelaminan|rias pengantin|catering)\b', 'EO & Wedding Organizer'),

    # 40. Travel Agent & Tiket
    (r'\b(travel agent|agen perjalanan|biro perjalanan|tiket|tour|wisata tur|umroh|haji)\b', 'Travel Agent & Tiket'),

    # 41. Service AC & Elektronik
    (r'\b(service ac|perbaikan ac|jual ac|instalasi ac|cuci ac)\b', 'Service AC & Elektronik'),

    # 42. Bengkel Sepeda
    (r'\b(bengkel sepeda|sepeda|bicycle|bike shop|toko sepeda)\b', 'Bengkel Sepeda'),

    # 43. Taman & Lapangan Olahraga
    (r'\b(lapangan|stadion|gelanggang|gor|taman bermain|futsal|badminton|tenis)\b', 'Taman & Lapangan Olahraga'),

    # 44. TK & PAUD
    (r'\b(tk|paud|taman kanak|playgroup|play group|kelompok bermain)\b', 'TK & PAUD'),

    # 45. Toko Pertanian & Pupuk
    (r'\b(pertanian|pupuk|pestisida|benih|bibit|pakan ternak|tani)\b', 'Toko Pertanian & Pupuk'),

    # 46. Kolam Pemancingan
    (r'\b(pemancingan|mancing|kolam pancing|ikan|perikanan)\b', 'Kolam Pemancingan'),

    # 47. Kantor Pemerintahan
    (r'\b(kantor kelurahan|kantor desa|kantor kecamatan|kantor camat|kantor lurah|kantor bupati|dinas|balai desa)\b', 'Kantor Pemerintahan'),

    # 48. Jasa Sedot WC & Plumbing
    (r'\b(sedot wc|plumbing|saluran air|pipa|tukang ledeng|septik|septic)\b', 'Jasa Sedot WC & Plumbing'),

    # 49. Toko Furniture & Meubel
    (r'\b(furniture|meubel|mebel|kursi|meja|lemari|sofa|interior|dekorasi rumah)\b', 'Toko Furniture & Meubel'),

    # 50. Toko Emas & Perhiasan
    (r'\b(emas|perhiasan|jewelry|jewellery|cincin|kalung|gelang emas)\b', 'Toko Emas & Perhiasan'),

    # 51. Depot Air Minum Isi Ulang
    (r'\b(depot air|air minum|isi ulang|galon|air mineral)\b', 'Depot Air Minum Isi Ulang'),

    # 52. Studio Musik & Latihan Band
    (r'\b(studio musik|latihan band|studio rekaman|recording|kursus musik|les musik)\b', 'Studio Musik & Latihan Band'),

    # 53. Counter Pulsa & PPOB
    (r'\b(pulsa|ppob|counter hp|konter|token listrik|paket data)\b', 'Counter Pulsa & PPOB'),

    # 54. Tukang Cukur Tradisional
    (r'\b(tukang cukur|pangkas rambut|pangkas|potong rambut)\b', 'Tukang Cukur Tradisional'),

    # 55. Toko Oleh-Oleh & Souvenir
    (r'\b(oleh-oleh|oleh oleh|souvenir|suvenir|cinderamata|khas daerah)\b', 'Toko Oleh-Oleh & Souvenir'),

    # 56. Jasa Cuci Mobil & Motor
    (r'\b(cuci mobil|cuci motor|car wash|carwash|steam mobil|salon mobil|detailing)\b', 'Jasa Cuci Mobil & Motor'),
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
