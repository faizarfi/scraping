import os
import re
import time
import logging
import threading
import urllib.parse

# Izinkan operasi sinkron Django ORM di thread yang memiliki event loop (Playwright)
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"

from django.db import close_old_connections
from django.utils import timezone
from .models import ScrapeJob, Place
from .category_normalizer import normalize_category

logger = logging.getLogger(__name__)

# Registry thread-safe untuk membatalkan proses scraping yang sedang berjalan
CANCELLED_JOB_IDS = set()
_cancel_lock = threading.Lock()


def request_cancel_job(job_id):
    """
    Tandai job agar segera dihentikan oleh thread worker scraper
    """
    with _cancel_lock:
        CANCELLED_JOB_IDS.add(int(job_id))
    try:
        job = ScrapeJob.objects.filter(id=job_id).first()
        if job and job.status in ['pending', 'running']:
            job.status = 'cancelled'
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'completed_at'])
            return True
    except Exception as e:
        logger.warning(f"Gagal update status cancel pada database untuk job {job_id}: {e}")
    return False


def is_job_cancelled(job_id):
    """
    Periksa apakah job diminta untuk dihentikan
    """
    with _cancel_lock:
        if int(job_id) in CANCELLED_JOB_IDS:
            return True
    try:
        job = ScrapeJob.objects.filter(id=job_id).only('status').first()
        if job and job.status == 'cancelled':
            with _cancel_lock:
                CANCELLED_JOB_IDS.add(int(job_id))
            return True
    except Exception:
        pass
    return False


def clear_cancelled_job(job_id):
    """
    Bersihkan ID job dari memory setelah thread berhenti
    """
    with _cancel_lock:
        CANCELLED_JOB_IDS.discard(int(job_id))


def parse_rating_reviews(parent, lines):
    """
    Ekstrak rating dan ulasan dari elemen bintang Google Maps atau baris teks
    """
    # Cara 1: Periksa span role='img' dengan aria-label (sangat presisi)
    try:
        star_spans = parent.locator("span[role='img'], span[aria-label*='bintang'], span[aria-label*='star']").all()
        for s in star_spans:
            aria = s.get_attribute("aria-label") or ""
            # Contoh: '4,8 bintang 2.398 Ulasan' atau '4.8 stars 2,398 reviews'
            match = re.search(r'([1-5][,\.]\d)\s*(?:bintang|stars?)(?:\s*([0-9\.\,]+))?', aria, re.I)
            if match:
                rating = float(match.group(1).replace(',', '.'))
                rev = int(re.sub(r'[^\d]', '', match.group(2))) if match.group(2) else 0
                return rating, rev
    except Exception:
        pass

    # Cara 2: Periksa baris teks kontainer seperti '4,8(2.398)'
    for line in lines:
        match = re.search(r'([1-5][,\.]\d)\s*\(([\d\.\,]+)\)', line)
        if match:
            try:
                rating_str = match.group(1).replace(',', '.')
                rating = float(rating_str)
                reviews_str = re.sub(r'[^\d]', '', match.group(2))
                reviews = int(reviews_str) if reviews_str else 0
                return rating, reviews
            except Exception:
                pass
    return None, 0


def parse_coordinates_from_url(url):
    """
    Ekstrak latitude dan longitude dari URL Google Maps
    """
    if not url:
        return None, None
    # Pola 1: !3d-6.244321!4d106.798123
    match = re.search(r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)', url)
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except Exception:
            pass
    # Pola 2: @-6.244321,106.798123
    match = re.search(r'@(-?\d+\.\d+),(-?\d+\.\d+)', url)
    if match:
        try:
            return float(match.group(1)), float(match.group(2))
        except Exception:
            pass
    return None, None

OPERATIONAL_KEYWORDS = {
    'buka', 'tutup', 'open', 'closed', 'buka 24 jam', 'open 24 hours',
    'buka sekarang', 'open now', 'tutup sementara', 'temporarily closed',
    'tutup permanen', 'permanently closed', 'buka segera', 'akan segera buka',
    'dine-in', 'takeaway', 'delivery', 'makan di tempat', 'bawa pulang',
    'pesan antar', 'drive-through', 'antar tanpa bertemu', 'no-contact delivery'
}

NON_CATEGORY_TERMS = {
    'bersponsor', 'sponsored', 'iklan', 'ad', 'ads',
    'sesuai untuk keluarga', 'ramah anak', 'populer', 'terpopuler',
    'indonesia', 'jawa', 'jawa tengah', 'jawa barat', 'jawa timur',
    'bisnis', 'tempat',
    # Tombol aksi & label antarmuka Google Maps
    'rute', 'directions', 'direction', 'situs web', 'website',
    'simpan', 'save', 'saved', 'bagikan', 'share',
    'telepon', 'call', 'pesan', 'message', 'ringkasan', 'overview',
    'tentang', 'about', 'nearby', 'di sekitar', 'mulai', 'start',
    'foto', 'photo', 'photos', 'menu', 'ulasan', 'review', 'reviews'
}


def clean_text_glyphs(text):
    """
    Hapus karakter Private Use Area Unicode (ikon Google Maps: \\uE000-\\uF8FF),
    karakter kontrol, dan simbol bullet murni.
    """
    if not text:
        return ""
    # Hapus karakter Private Use Area Unicode (ikon font Google Maps)
    cleaned = re.sub(r'[\ue000-\uf8ff]', '', text)
    # Hapus karakter kontrol non-printable
    cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
    # Normalkan spasi
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    # Jika hanya simbol tanda baca / bullet / titik saja
    if re.match(r'^[\s\·\•\-\.\,\:\;\|\/\\]*$', cleaned):
        return ""
    return cleaned


def is_operational_or_status(text):
    """
    Periksa apakah suatu teks adalah status jam operasional Google Maps (Buka/Tutup/dsb)
    """
    if not text:
        return True
    t = clean_text_glyphs(text).strip().lower()
    if not t:
        return True
    if t in OPERATIONAL_KEYWORDS:
        return True
    if re.search(r'^(buka|tutup|open|closed)\b', t):
        return True
    if any(k in t for k in ['tutup pukul', 'buka pukul', 'buka 24 jam', 'closes at', 'opens at', 'closes soon', 'opens soon']):
        return True
    if re.search(r'\b(pukul|\bpm\b|\bam\b)\s*\d', t):
        return True
    return False


def is_rating_review_text(text):
    """
    Periksa apakah teks memuat informasi rating atau ulasan
    (misal: 'Tidak ada ulasan', '4,8 bintang', '4.5(120)', '(1.234)', dsb)
    """
    if not text:
        return False
    t = clean_text_glyphs(text).strip().lower()
    if not t:
        return True
    # Teks tanpa ulasan (Indonesia / English)
    if any(phrase in t for phrase in [
        'tidak ada ulasan', 'belum ada ulasan', 'tanpa ulasan',
        'no reviews', 'no review', 'no rating'
    ]):
        return True
    # Pola review dengan nomor urut seperti '1. Tidak ada ulasan'
    if re.search(r'^\d+[\.\)]\s*(?:tidak ada ulasan|belum ada ulasan|no reviews?)', t):
        return True
    # Pola rating angka seperti '4,8' atau '4.5' atau '4,8(120)'
    if re.search(r'^[1-5][,\.]\d\s*(?:\([0-9\.\,]+\))?$', t):
        return True
    # Pola jumlah ulasan dalam kurung seperti '(1.234)'
    if re.search(r'^\([0-9\.\,]+\)$', t):
        return True
    # Pola ulasan/bintang seperti '120 ulasan', '4,5 bintang', '5 stars'
    if re.search(r'^\d+[\.,]?\d*\s*(?:ulasan|reviews?|bintang|stars?)$', t):
        return True
    return False


def is_likely_address(text):
    """
    Evaluasi apakah teks adalah alamat fisik atau Plus Code Google Maps valid
    """
    if not text:
        return False
    t = clean_text_glyphs(text).strip()
    if not t or is_operational_or_status(t) or is_rating_review_text(t):
        return False
    t_lower = t.lower()
    # Jangan anggap kategori hotel bintang sebagai alamat
    if re.search(r'^hotel\s+bintang\s+\d', t_lower):
        return False
    # Jangan anggap harga kamar sebagai alamat
    if re.search(r'(?:rp\s*[\d\.]+|\/malam|per malam)', t_lower):
        return False
    # Plus Code Google Maps (misal: '93M3+Q7J', 'CW6G+PXG, Karanganyar')
    if re.search(r'\b[2-9CFGHJMPQRVWX]{4,8}\+[2-9CFGHJMPQRVWX]{2,3}\b', t, re.I):
        return True
    # Kata kunci alamat fisik umum di Indonesia
    if any(k in t_lower for k in [
        'jl.', 'jalan', 'raya', 'no.', 'rt.', 'rw.', 'gang', 'gg.',
        'kelurahan', 'kecamatan', 'kabupaten', 'kota', 'komplek',
        'blok', 'dusun', 'desa', 'perumahan', 'perum'
    ]):
        return True
    # Format kode pos 5 digit
    if re.search(r'\b\d{5}\b', t):
        return True
    # Alamat yang memuat nomor dan cukup panjang
    if any(char.isdigit() for char in t) and len(t) >= 15 and not t_lower.startswith('hotel'):
        return True
    return False


def is_valid_category_candidate(text):
    """
    Validasi ketat apakah suatu string layak menjadi nama kategori bisnis
    """
    if not text:
        return False
    t = clean_text_glyphs(text).strip()
    if not t or len(t) < 2 or len(t) > 50:
        return False
    t_lower = t.lower()
    if is_operational_or_status(t_lower) or is_rating_review_text(t_lower):
        return False
    if t_lower in NON_CATEGORY_TERMS:
        return False
    # Jangan terima kutipan testimoni atau pertanyaan (misal: '"Bisa order untuk di kirim?"')
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")) or '?' in t:
        return False
    # Jangan terima harga atau tarif hotel
    if re.search(r'(?:rp\s*[\d\.]+|\/malam|per malam|\$\$\$?)', t_lower):
        return False
    # Jangan terima jika murni alamat atau plus code
    if is_likely_address(t):
        return False
    # Tolak Plus Code Google Maps (misal 'CVCW+RC8' atau 'CVCWRC8' atau '93M3+Q7J')
    if re.match(r'^[2-9A-Z]{4,8}\+?[2-9A-Z]{2,4}$', t, re.I):
        return False
    # Tolak kode alfanumerik kapital tanpa huruf vokal (seperti 'CVCWRC8')
    if len(t) >= 5 and re.match(r'^[A-Z0-9]+$', t) and not any(v in t_lower for v in ['a', 'i', 'u', 'e', 'o']):
        return False
    # Harus memuat setidaknya satu huruf alfabet
    if not re.search(r'[a-zA-Z]', t):
        return False
    # Jangan terima nomor telepon
    if re.search(r'^[\d\s\-\+\(\)]{8,}$', t):
        return False
    return True


def parse_category_and_address(lines, place_name=""):
    """
    Ekstrak kategori dan alamat dari teks kartu Google Maps secara akurat,
    dengan menyaring teks status jam operasional, rating/ulasan ('Tidak ada ulasan'),
    glyph ikon Unicode, dan badge non-kategori.
    """
    category = ""
    address = ""

    clean_lines = []
    p_name_lower = clean_text_glyphs(place_name or "").strip().lower()

    for line in lines:
        cleaned = clean_text_glyphs(line).strip()
        if not cleaned:
            continue
        if p_name_lower and cleaned.lower() == p_name_lower:
            continue
        # Hanya lewati jika baris murni tanpa pemisah dan berstatus operasional/ulasan
        if '·' not in cleaned and '•' not in cleaned:
            if is_operational_or_status(cleaned) or is_rating_review_text(cleaned):
                continue
        clean_lines.append(cleaned)

    for cleaned in clean_lines:
        # Periksa apakah ada pemisah · atau •
        if '·' in cleaned or '•' in cleaned:
            raw_parts = [clean_text_glyphs(p).strip() for p in re.split(r'[·•]', cleaned)]
            valid_parts = [p for p in raw_parts if p and not is_operational_or_status(p) and not is_rating_review_text(p)]

            for p in valid_parts:
                if not category and is_valid_category_candidate(p):
                    category = p
                    continue
                if not address and is_likely_address(p):
                    address = p
                    continue
        else:
            if not category and is_valid_category_candidate(cleaned):
                category = cleaned
            elif not address and is_likely_address(cleaned):
                address = cleaned

        if category and address:
            break

    # Fallback jika alamat belum ditemukan
    if not address:
        for cleaned in clean_lines:
            if is_operational_or_status(cleaned) or is_rating_review_text(cleaned):
                continue
            if is_likely_address(cleaned):
                address = cleaned
                break

    # Sanitasi jika alamat masih menggabungkan kategori (misal: 'Kantor Perusahaan · 93M3+Q7J')
    if address and ('·' in address or '•' in address):
        p_addr = [clean_text_glyphs(x).strip() for x in re.split(r'[·•]', address) if clean_text_glyphs(x).strip()]
        for part in p_addr:
            if not category and is_valid_category_candidate(part):
                category = part
            elif is_likely_address(part):
                address = part

    # Sanitasi akhir: jika kategori tertukar ke alamat (misal: 'Hotel bintang 3' atau 'Biro Perjalanan')
    if not category and address and is_valid_category_candidate(address) and not is_likely_address(address):
        category = address
        address = ""

    # Pastikan kategori valid
    if not is_valid_category_candidate(category):
        category = ""

    # Pastikan alamat valid
    if is_operational_or_status(address) or is_rating_review_text(address) or re.search(r'(?:rp\s*[\d\.]+|\/malam)', address.lower()):
        address = ""

    return category, address


def parse_phone_and_website(parent, lines):
    """
    Ekstrak nomor telepon dan URL website dari elemen kartu Google Maps
    """
    phone = ""
    website = ""

    for line in lines:
        cleaned = line.strip()
        # Pola nomor telepon Indonesia: 08xx, +62xx, (02xx), dsb.
        m = re.search(r'((?:\+62|62|08|\(0\d{2,4}\)|0\d{2,4})[\d\s\-\(\)]{6,18}\d)', cleaned)
        if m:
            candidate = re.sub(r'[^\d+]', '', m.group(1))
            if 8 <= len(candidate) <= 16:
                phone = m.group(1).strip()
                break

    try:
        web_link = parent.locator("a[data-value*='Website'], a[aria-label*='Situs'], a[aria-label*='Website'], a[href*='google.com/url']").first
        if web_link.count() > 0:
            href = web_link.get_attribute("href") or ""
            if "google.com/url?" in href:
                parsed = urllib.parse.urlparse(href)
                qs = urllib.parse.parse_qs(parsed.query)
                target = qs.get('q', [''])[0]
                if target.startswith('http'):
                    website = target
            elif href.startswith("http") and "google.com" not in href:
                website = href
    except Exception:
        pass

    return phone, website


# Pemetaan resmi kecamatan per kabupaten untuk deep grid scraping hingga ke pelosok
LOCATION_DISTRICTS_MAP = {
    'karanganyar': [
        'Colomadu', 'Gondangrejo', 'Jaten', 'Jatipuro', 'Jatiyoso', 
        'Jenawi', 'Jumantono', 'Jumapolo', 'Karanganyar', 'Karangpandan', 
        'Kebakkramat', 'Kerjo', 'Matesih', 'Mojogedang', 'Ngargoyoso', 
        'Tasikmadu', 'Tawangmangu'
    ]
}


def get_districts_for_location(location_str):
    """
    Kembalikan daftar seluruh kecamatan resmi untuk lokasi/kabupaten tertentu jika tersedia
    """
    if not location_str:
        return []
    loc_lower = location_str.lower()
    for key, districts in LOCATION_DISTRICTS_MAP.items():
        if key in loc_lower:
            return districts
    return []


def resolve_district_from_text(address_text, query_text="", preset_district=""):
    """
    Deteksi nama kecamatan secara cerdas & universal untuk kota manapun di Indonesia:
    1. Ekstraksi otomatis dari teks alamat menggunakan pola regex 'Kecamatan X' atau 'Kec. X'
    2. Cek apakah ada kecamatan yang dikenal di dalam teks alamat
    3. Jika alamat tidak mencantumkan nama kecamatan, gunakan preset_district (dari query target)
    4. Cek query_text jika masih belum ditemukan
    """
    combined_addr = address_text or ""

    # 1. Deteksi regex pada teks alamat: "Kecamatan Sukajadi", "Kec. Tebet", dll.
    m = re.search(r'Kec(?:amatan|\.)\s+([A-Za-z0-9\s]+?)(?:,|$|\.|\d|\-)', combined_addr, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        if 3 <= len(name) <= 30:
            return name.title()

    known_districts = [
        'Colomadu', 'Gondangrejo', 'Jaten', 'Jatipuro', 'Jatiyoso', 
        'Jenawi', 'Jumantono', 'Jumapolo', 'Karanganyar', 'Karangpandan', 
        'Kebakkramat', 'Kerjo', 'Matesih', 'Mojogedang', 'Ngargoyoso', 
        'Tasikmadu', 'Tawangmangu', 'Tebet', 'Kebayoran Baru', 'Kebayoran Lama',
        'Cilandak', 'Setiabudi', 'Mampang Prapatan', 'Pancoran', 'Pasar Minggu'
    ]
    for d in known_districts:
        if d.lower() in combined_addr.lower():
            return d

    # 2. Jika tidak ada di alamat, gunakan preset_district (misal dari subdistrict query)
    if preset_district and preset_district.strip():
        return preset_district.strip()

    # 3. Cek query_text jika belum ada
    combined_query = query_text or ""
    m_q = re.search(r'Kec(?:amatan|\.)\s+([A-Za-z0-9\s]+?)(?:,|$|\.|\d|\-)', combined_query, re.IGNORECASE)
    if m_q:
        name = m_q.group(1).strip()
        if 3 <= len(name) <= 30:
            return name.title()

    for d in known_districts:
        if d.lower() in combined_query.lower():
            return d

    return "-"


def check_is_duplicate(name, lat, lng, address=None):
    """
    Aturan Deduplikasi:
    HANYA anggap duplikat jika NAMA dan GEOLOKASI (lat & lng) KEDUANYA SAMA.
    - Jika nama sama tapi koordinat berbeda -> BUKAN duplikat (cabang berbeda).
    - Jika koordinat sama tapi nama berbeda -> BUKAN duplikat (tempat berbeda dalam 1 gedung/area).
    """
    if not name:
        return True

    name_clean = name.strip()

    # Cek jika ada koordinat
    if lat is not None and lng is not None:
        candidates = Place.objects.filter(name__iexact=name_clean)
        for p in candidates:
            if p.latitude is not None and p.longitude is not None:
                # Toleransi ~25 meter
                if abs(p.latitude - lat) < 0.00025 and abs(p.longitude - lng) < 0.00025:
                    return True
        # Nama sama tetapi koordinat berbeda -> Cabang baru, simpan!
        return False

    # Fallback jika koordinat tidak terbaca: cek kesamaan nama & alamat
    if address and address.strip():
        candidates = Place.objects.filter(name__iexact=name_clean)
        for p in candidates:
            if p.address and p.address.strip().lower() == address.strip().lower():
                return True
        return False

    # Jika koordinat dan alamat keduanya tidak terbaca: cek apakah nama persis sudah ada
    if Place.objects.filter(name__iexact=name_clean).exists():
        return True

    return False


def build_full_query(job):
    """
    Membentuk query pencarian presisi dengan dukungan Kecamatan dan Kota
    """
    query = job.query.strip()
    district = job.district.strip() if job.district else ""
    location = job.location.strip() if job.location else ""

    parts = [query]
    if district:
        if not district.lower().startswith('kecamatan'):
            parts.append(f"Kecamatan {district}")
        else:
            parts.append(district)
    if location:
        parts.append(location)

    if len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        return f"{parts[0]} di {parts[1]}"
    else:
        # e.g. "Cafe di Kecamatan Tebet, Jakarta Selatan"
        return f"{parts[0]} di {parts[1]}, {parts[2]}"


def scrape_single_category(worker_id, page, cat_name, cat_idx, total_cats, job_id, is_unlimited, per_category_target, max_scroll_attempts, shared_stats, db_lock, target_district=None):
    """
    Eksekusi scraping untuk 1 kategori spesifik di dalam worker tab tertentu.
    Mendukung target_district untuk pencarian mendalam per kecamatan (Deep Grid).
    """
    from .models import ScrapeJob, Place

    job = ScrapeJob.objects.filter(id=job_id).first()
    if not job or is_job_cancelled(job_id):
        return

    # Gunakan target_district jika dioper (dari deep grid), jika tidak fallback ke job.district
    active_district = (target_district if target_district is not None else (job.district or "")).strip()

    parts = [cat_name]
    if active_district:
        if not active_district.lower().startswith('kecamatan'):
            parts.append(f"Kecamatan {active_district}")
        else:
            parts.append(active_district)
    if job.location:
        parts.append(job.location)

    if len(parts) == 1:
        item_full_query = parts[0]
    elif len(parts) == 2:
        item_full_query = f"{parts[0]} di {parts[1]}"
    else:
        item_full_query = f"{parts[0]} di {parts[1]}, {parts[2]}"

    logger.info(f"[Tab-{worker_id}] [{cat_idx}/{total_cats}] Scraping: '{item_full_query}' (Target: {'Maksimal' if is_unlimited else per_category_target})")
    encoded_query = urllib.parse.quote_plus(item_full_query)
    search_url = f"https://www.google.com/maps/search/{encoded_query}/"

    try:
        page.goto(search_url, timeout=35000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
    except Exception as nav_err:
        logger.warning(f"[Tab-{worker_id}] Navigasi timeout untuk '{item_full_query}': {nav_err}")
        return

    # Tangani dialog consent / cookie Google jika muncul
    try:
        consent_btn = page.locator("button:has-text('Accept all'), button:has-text('Setuju semua'), button:has-text('Tolak semua'), form[action*='consent'] button").first
        if consent_btn.count() > 0 and consent_btn.is_visible():
            consent_btn.click()
            page.wait_for_timeout(1500)
    except Exception:
        pass

    scroll_count = 0
    prev_len = 0
    consecutive_same_len = 0

    while scroll_count < max_scroll_attempts:
        if is_job_cancelled(job_id):
            return

        page.mouse.move(250, 350)
        page.mouse.wheel(0, 3500)
        page.wait_for_timeout(1600)
        scroll_count += 1

        links = page.locator("div[role='feed'] a[href*='/maps/place/']").all()
        curr_len = len(links)
        if not is_unlimited and curr_len >= per_category_target:
            break

        if curr_len == prev_len:
            consecutive_same_len += 1
            # Nudge scroll: jika data tampak berhenti pada kali ke-2, gerakkan scroll ke atas sedikit lalu hentak ke bawah
            if consecutive_same_len == 2:
                try:
                    page.mouse.wheel(0, -800)
                    page.wait_for_timeout(800)
                    page.mouse.wheel(0, 4000)
                    page.wait_for_timeout(1500)
                except Exception:
                    pass
            if consecutive_same_len >= 4:
                break
        else:
            consecutive_same_len = 0
        prev_len = curr_len

        end_text = page.locator("text='Anda telah mencapai akhir daftar', text=\"You've reached the end of the list\"")
        if end_text.count() > 0:
            break

    if is_job_cancelled(job_id):
        return

    links = page.locator("div[role='feed'] a[href*='/maps/place/']").all()

    # Fallback jika Google Maps langsung membuka halaman detail 1 tempat (exact match)
    if not links and "/maps/place/" in page.url:
        try:
            h1_el = page.locator("h1").first
            if h1_el.count() > 0:
                s_name = h1_el.inner_text().strip()
                if s_name:
                    s_href = page.url
                    s_lat, s_lng = parse_coordinates_from_url(s_href)
                    main_panel = page.locator("div[role='main']").first
                    panel_text = main_panel.inner_text() if main_panel.count() > 0 else page.inner_text()
                    panel_lines = [l.strip() for l in panel_text.split("\n") if l.strip()]

                    s_rating, s_reviews = parse_rating_reviews(main_panel, panel_lines)
                    s_category, s_address = parse_category_and_address(panel_lines, place_name=s_name)
                    s_phone, s_website = parse_phone_and_website(main_panel, panel_lines)
                    s_district = resolve_district_from_text(s_address, item_full_query, active_district)

                    s_clean_name = s_name.strip().lower()
                    if s_lat is not None and s_lng is not None:
                        s_key = (s_clean_name, round(s_lat, 4), round(s_lng, 4))
                    else:
                        s_key = (s_clean_name, (s_address or '').strip().lower())

                    with db_lock:
                        if s_href not in shared_stats['seen_urls'] and s_key not in shared_stats['seen_places']:
                            if not check_is_duplicate(s_name, s_lat, s_lng, s_address):
                                shared_stats['seen_urls'].add(s_href)
                                shared_stats['seen_places'].add(s_key)
                                raw_cat = s_category.strip() if is_valid_category_candidate(s_category) else cat_name
                                final_cat = normalize_category(raw_cat, item_full_query)
                                final_addr = s_address.strip() if s_address and not is_operational_or_status(s_address) and not is_rating_review_text(s_address) else ""
                                Place.objects.create(
                                    job_id=job_id,
                                    name=s_name,
                                    category=final_cat,
                                    district=s_district,
                                    address=final_addr,
                                    phone=s_phone,
                                    website=s_website,
                                    rating=s_rating,
                                    reviews_count=s_reviews,
                                    google_maps_url=s_href,
                                    latitude=s_lat,
                                    longitude=s_lng,
                                    search_query=item_full_query
                                )
                                shared_stats['scraped_count'] += 1
                                ScrapeJob.objects.filter(id=job_id).update(total_scraped=shared_stats['scraped_count'])
        except Exception as single_err:
            logger.warning(f"[Tab-{worker_id}] Gagal ekstrak tempat tunggal: {single_err}")

    cat_scraped = 0
    for item in links:
        if is_job_cancelled(job_id):
            return
        if not is_unlimited and cat_scraped >= per_category_target:
            break

        href = item.get_attribute("href") or ""
        if not href:
            continue

        name = item.get_attribute("aria-label") or ""
        if not name:
            name = item.inner_text().split("\n")[0].strip()
        # Lewati thumbnail foto atau label navigasi
        if not name or name.lower().startswith('foto ') or name.lower().startswith('photo '):
            continue

        with db_lock:
            if href in shared_stats['seen_urls']:
                continue
            shared_stats['seen_urls'].add(href)

        parent = item.locator("xpath=..")
        parent_lines = [l.strip() for l in parent.inner_text().split("\n") if l.strip()]

        rating, reviews = parse_rating_reviews(parent, parent_lines)
        category, address = parse_category_and_address(parent_lines, place_name=name)
        phone, website = parse_phone_and_website(parent, parent_lines)
        lat, lng = parse_coordinates_from_url(href)

        district_name = resolve_district_from_text(address, item_full_query, active_district)

        name_clean = name.strip().lower()
        if lat is not None and lng is not None:
            place_key = (name_clean, round(lat, 4), round(lng, 4))
        else:
            place_key = (name_clean, (address or '').strip().lower())

        with db_lock:
            if place_key in shared_stats['seen_places']:
                continue
            if check_is_duplicate(name, lat, lng, address):
                continue

            shared_stats['seen_places'].add(place_key)

            raw_category = category.strip() if is_valid_category_candidate(category) else cat_name
            final_category = normalize_category(raw_category, item_full_query)
            final_address = address.strip() if address and not is_operational_or_status(address) and not is_rating_review_text(address) else ""

            Place.objects.create(
                job_id=job_id,
                name=name,
                category=final_category,
                district=district_name,
                address=final_address,
                phone=phone,
                website=website,
                rating=rating,
                reviews_count=reviews,
                google_maps_url=href,
                latitude=lat,
                longitude=lng,
                search_query=item_full_query
            )
            shared_stats['scraped_count'] += 1
            cat_scraped += 1

            if shared_stats['scraped_count'] % 2 == 0:
                ScrapeJob.objects.filter(id=job_id).update(total_scraped=shared_stats['scraped_count'])


def run_playwright_scraper(job_id, target_count=30):
    """
    Worker Playwright Multi-Tab Paralel:
    Membagi daftar kategori ke dalam antrean (Queue) yang dikerjakan secara simultan
    oleh 2-3 worker tab paralel, meningkatkan kecepatan scraping hingga 3x lipat.
    """
    import queue
    from playwright.sync_api import sync_playwright

    close_old_connections()
    try:
        job = ScrapeJob.objects.get(id=job_id)
        job.status = 'running'
        job.save(update_fields=['status'])
    except ScrapeJob.DoesNotExist:
        return

    sub_queries = [q.strip() for q in job.query.split(',') if q.strip()]
    if not sub_queries:
        sub_queries = [job.query.strip()]

    is_unlimited = (target_count <= 0 or target_count >= 999)
    per_category_target = 999999 if is_unlimited else target_count
    max_scroll_attempts = 45 if is_unlimited else max(10, (per_category_target // 5) + 5)

    task_items = []
    # Jika pengguna memilih "Semua Kecamatan" (job.district kosong) dan wilayah memiliki mapping kecamatan resmi:
    # Lakukan dekomposisi per kecamatan secara menyeluruh (Deep Grid Iteration) agar menjangkau pelosok
    districts_list = get_districts_for_location(job.location) if not (job.district and job.district.strip()) else []

    if districts_list:
        for cat_name in sub_queries:
            for dist in districts_list:
                task_items.append((cat_name, dist))
            # Tambahkan pencarian kabupaten umum untuk menjangkau tempat perbatasan & pusat
            task_items.append((cat_name, ""))
    else:
        single_dist = job.district.strip() if job.district else ""
        for cat_name in sub_queries:
            task_items.append((cat_name, single_dist))

    total_tasks = len(task_items)
    # Tentukan jumlah worker tab paralel (1 tab jika hanya 1 tugas, hingga 3 tab untuk multi-tugas)
    num_workers = min(3, max(1, total_tasks))

    logger.info(
        f"Memulai Playwright Multi-Tab Scraping untuk job {job_id} "
        f"({len(sub_queries)} kategori, {total_tasks} total tugas pencarian dengan {num_workers} worker paralel, "
        f"target: {'UNLIMITED' if is_unlimited else per_category_target})"
    )

    task_queue = queue.Queue()
    for task_idx, (cat_name, target_dist) in enumerate(task_items, start=1):
        task_queue.put((task_idx, cat_name, target_dist))

    db_lock = threading.Lock()
    worker_errors = []
    shared_stats = {
        'scraped_count': 0,
        'seen_urls': set(),
        'seen_places': set()
    }

    # Pre-populate seen places dari database untuk mempercepat deduplikasi
    try:
        for p_name, p_lat, p_lng, p_addr in Place.objects.values_list('name', 'latitude', 'longitude', 'address')[:5000]:
            if p_name:
                p_clean = p_name.strip().lower()
                if p_lat is not None and p_lng is not None:
                    shared_stats['seen_places'].add((p_clean, round(p_lat, 4), round(p_lng, 4)))
                else:
                    shared_stats['seen_places'].add((p_clean, (p_addr or '').strip().lower()))
    except Exception:
        pass

    def worker_loop(worker_id):
        close_old_connections()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu"
                    ]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    locale="id-ID",
                    viewport={"width": 1280, "height": 850}
                )
                page = context.new_page()

                while not task_queue.empty():
                    if is_job_cancelled(job_id):
                        break
                    try:
                        task_idx, cat_name, target_dist = task_queue.get_nowait()
                    except queue.Empty:
                        break

                    try:
                        scrape_single_category(
                            worker_id=worker_id,
                            page=page,
                            cat_name=cat_name,
                            cat_idx=task_idx,
                            total_cats=total_tasks,
                            job_id=job_id,
                            is_unlimited=is_unlimited,
                            per_category_target=per_category_target,
                            max_scroll_attempts=max_scroll_attempts,
                            shared_stats=shared_stats,
                            db_lock=db_lock,
                            target_district=target_dist
                        )
                    except Exception as cat_err:
                        logger.error(f"[Tab-{worker_id}] Error pada '{cat_name}' ({target_dist or 'Umum'}): {cat_err}", exc_info=True)
                    finally:
                        task_queue.task_done()

                browser.close()
        except Exception as proc_err:
            logger.error(f"[Tab-{worker_id}] Browser worker error: {proc_err}", exc_info=True)
            with db_lock:
                worker_errors.append(str(proc_err))
        finally:
            close_old_connections()

    # Jalankan worker threads secara paralel
    worker_threads = []
    for wid in range(1, num_workers + 1):
        t = threading.Thread(target=worker_loop, args=(wid,), daemon=True)
        worker_threads.append(t)
        t.start()

    # Tunggu semua worker selesai
    for t in worker_threads:
        t.join()

    # Finalisasi status job
    job.refresh_from_db()
    total_final = shared_stats['scraped_count']
    if is_job_cancelled(job_id):
        job.mark_cancelled(total=total_final)
        logger.info(f"Job {job_id} berhasil dihentikan atas permintaan pengguna ({total_final} tempat tersimpan).")
    elif total_final == 0 and len(worker_errors) >= num_workers:
        err_detail = f"Gagal menjalankan peramban Playwright: {'; '.join(worker_errors[:2])}"
        job.mark_failed(err_detail)
        logger.error(f"Job {job_id} gagal: {err_detail}")
    else:
        job.mark_completed(total_final)
        logger.info(f"Job {job_id} berhasil selesai dengan {total_final} tempat menggunakan {num_workers} tab paralel.")

    clear_cancelled_job(job_id)
    close_old_connections()



def run_places_api_scraper(job_id, api_key, target_count=30):
    """
    Fungsi worker Google Places API (New) resmi
    """
    import requests
    close_old_connections()
    try:
        job = ScrapeJob.objects.get(id=job_id)
        job.status = 'running'
        job.save()
    except ScrapeJob.DoesNotExist:
        return

    full_query = build_full_query(job)

    logger.info(f"Memulai Google Places API (New) untuk job {job_id}: {full_query}")
    scraped_count = 0
    next_page_token = None

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key.strip(),
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.nationalPhoneNumber,places.websiteUri,places.location,places.primaryTypeDisplayName,places.googleMapsUri,nextPageToken"
    }

    try:
        while scraped_count < target_count:
            if is_job_cancelled(job_id):
                break

            payload = {
                "textQuery": full_query,
                "pageSize": min(20, target_count - scraped_count)
            }
            if next_page_token:
                payload["pageToken"] = next_page_token

            resp = requests.post(url, headers=headers, json=payload, timeout=20)
            if resp.status_code != 200:
                raise Exception(f"Places API Error ({resp.status_code}): {resp.text}")

            data = resp.json()
            places_list = data.get("places", [])
            if not places_list:
                break

            for p_data in places_list:
                if is_job_cancelled(job_id) or scraped_count >= target_count:
                    break

                display_name = p_data.get("displayName", {}).get("text", "")
                if not display_name:
                    continue

                category = p_data.get("primaryTypeDisplayName", {}).get("text", "")
                address = p_data.get("formattedAddress", "")
                phone = p_data.get("nationalPhoneNumber", "")
                website = p_data.get("websiteUri", "")
                rating = p_data.get("rating")
                reviews = p_data.get("userRatingCount", 0)
                maps_url = p_data.get("googleMapsUri", "")
                loc = p_data.get("location", {})
                lat = loc.get("latitude")
                lng = loc.get("longitude")

                # Cek aturan deduplikasi: HANYA skip jika Nama DAN Geolokasi SAMA
                if check_is_duplicate(display_name, lat, lng, address):
                    continue

                place = Place.objects.create(
                    job=job,
                    name=display_name,
                    category=category,
                    district=job.district,
                    address=address,
                    phone=phone,
                    website=website,
                    rating=rating,
                    reviews_count=reviews,
                    google_maps_url=maps_url,
                    latitude=lat,
                    longitude=lng,
                    search_query=full_query
                )
                scraped_count += 1
                job.total_scraped = scraped_count
                job.save(update_fields=['total_scraped'])


            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
            time.sleep(1.5)

        if is_job_cancelled(job_id):
            job.mark_cancelled(total=scraped_count)
            logger.info(f"Places API job {job_id} dihentikan atas permintaan pengguna ({scraped_count} tempat tersimpan).")
            return

        job.mark_completed(scraped_count)
        logger.info(f"Places API job {job_id} selesai dengan {scraped_count} tempat.")

    except Exception as e:
        logger.error(f"Error pada Places API untuk job {job_id}: {str(e)}", exc_info=True)
        job.mark_failed(str(e))
    finally:
        clear_cancelled_job(job_id)
        close_old_connections()


def start_scraping_async(job_id, api_key=None):
    """
    Jalankan scraper di thread terpisah agar halaman web tetap responsif
    """
    job = ScrapeJob.objects.get(id=job_id)
    if job.engine == 'places_api' and api_key:
        t = threading.Thread(target=run_places_api_scraper, args=(job_id, api_key, job.target_count), daemon=True)
    else:
        t = threading.Thread(target=run_playwright_scraper, args=(job_id, job.target_count), daemon=True)
    t.start()
    return t
