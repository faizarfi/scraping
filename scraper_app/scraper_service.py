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

def parse_category_and_address(lines):
    """
    Cari baris yang memuat kategori dan alamat (biasanya dipisahkan dengan tanda titik tengah ·)
    """
    category = ""
    address = ""
    
    for line in lines:
        cleaned = line.strip()
        # Periksa apakah ada pemisah · atau •
        if '·' in cleaned or '•' in cleaned:
            parts = [p.strip() for p in re.split(r'[·•]', cleaned) if p.strip()]
            if parts:
                # Bagian pertama biasanya kategori (Restoran, Kafe, Kedai Kopi, Toko, dll.)
                first = parts[0]
                if len(first) < 40 and not any(char.isdigit() for char in first[:5]):
                    category = first
                # Cari bagian yang mengandung kata jalan / alamat atau paling panjang
                for p in parts[1:]:
                    if any(k in p.lower() for k in ['jl.', 'jalan', 'rt.', 'rw.', 'no.', 'kelurahan', 'kecamatan', 'kabupaten', 'kota']) or len(p) > 15:
                        address = p
                        break
                if not address and len(parts) > 1:
                    address = parts[-1]
                if category and address:
                    return category, address

    # Fallback: jika tidak ada pemisah ·
    for line in lines:
        cleaned = line.strip()
        if any(k in cleaned.lower() for k in ['jl.', 'jalan', 'raya', 'no.', 'rt.', 'rw.']):
            address = cleaned
            break

    return category, address


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


def run_playwright_scraper(job_id, target_count=30):
    """
    Fungsi worker Playwright untuk scraping data Google Maps
    """
    from playwright.sync_api import sync_playwright
    
    close_old_connections()
    try:
        job = ScrapeJob.objects.get(id=job_id)
        job.status = 'running'
        job.save()
    except ScrapeJob.DoesNotExist:
        return

    sub_queries = [q.strip() for q in job.query.split(',') if q.strip()]
    if not sub_queries:
        sub_queries = [job.query.strip()]

    # Mode Target:
    # Jika target_count <= 0 atau >= 999 -> Mode SEBANYAK-BANYAKNYA (Maksimal s/d Habis di Google Maps)
    # Jika target_count > 0 -> Target penuh per kategori (TIDAK DIBAGI!)
    is_unlimited = (target_count <= 0 or target_count >= 999)
    if is_unlimited:
        per_category_target = 999999
        max_scroll_attempts = 45
    else:
        per_category_target = target_count
        max_scroll_attempts = max(10, (per_category_target // 5) + 5)

    logger.info(f"Memulai Playwright scraping untuk job {job_id} ({len(sub_queries)} kategori, target {'UNLIMITED' if is_unlimited else per_category_target}): {sub_queries}")
    scraped_count = 0
    seen_urls = set()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                locale="id-ID",
                viewport={"width": 1280, "height": 850}
            )
            page = context.new_page()

            for cat_idx, cat_name in enumerate(sub_queries, start=1):
                if is_job_cancelled(job_id):
                    logger.info(f"Job {job_id} dibatalkan oleh pengguna sebelum kategori '{cat_name}'.")
                    break

                # Bentuk query pencarian presisi untuk kategori ini
                parts = [cat_name]
                if job.district:
                    if not job.district.lower().startswith('kecamatan'):
                        parts.append(f"Kecamatan {job.district}")
                    else:
                        parts.append(job.district)
                if job.location:
                    parts.append(job.location)

                if len(parts) == 1:
                    item_full_query = parts[0]
                elif len(parts) == 2:
                    item_full_query = f"{parts[0]} di {parts[1]}"
                else:
                    item_full_query = f"{parts[0]} di {parts[1]}, {parts[2]}"

                logger.info(f"[{cat_idx}/{len(sub_queries)}] Scraping: '{item_full_query}' (target: {'Sebanyak-banyaknya' if is_unlimited else per_category_target})")
                encoded_query = urllib.parse.quote_plus(item_full_query)
                search_url = f"https://www.google.com/maps/search/{encoded_query}/"

                try:
                    page.goto(search_url, timeout=35000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                except Exception as nav_err:
                    logger.warning(f"Navigasi timeout untuk '{item_full_query}': {nav_err}")
                    continue

                # Scroll feed secara bertahap sampai target atau ujung feed tercapai
                scroll_count = 0
                prev_len = 0
                consecutive_same_len = 0

                while scroll_count < max_scroll_attempts:
                    if is_job_cancelled(job_id):
                        logger.info(f"Job {job_id} dibatalkan oleh pengguna saat scrolling '{cat_name}'.")
                        break

                    page.mouse.move(250, 350)
                    page.mouse.wheel(0, 3500)
                    page.wait_for_timeout(1800)
                    scroll_count += 1

                    links = page.locator("div[role='feed'] a[href*='/maps/place/']").all()
                    curr_len = len(links)
                    if not is_unlimited and curr_len >= per_category_target:
                        break

                    if curr_len == prev_len:
                        consecutive_same_len += 1
                        if consecutive_same_len >= 3:
                            break
                    else:
                        consecutive_same_len = 0
                    prev_len = curr_len

                    end_text = page.locator("text='Anda telah mencapai akhir daftar', text=\"You've reached the end of the list\"")
                    if end_text.count() > 0:
                        break

                if is_job_cancelled(job_id):
                    break

                # Ekstrak data dari kartu yang ditemukan untuk kategori ini
                links = page.locator("div[role='feed'] a[href*='/maps/place/']").all()
                cat_scraped = 0

                for item in links:
                    if is_job_cancelled(job_id):
                        logger.info(f"Job {job_id} dibatalkan oleh pengguna saat ekstraksi data.")
                        break

                    if not is_unlimited and cat_scraped >= per_category_target:
                        break

                    href = item.get_attribute("href") or ""
                    if not href or href in seen_urls:
                        continue
                    seen_urls.add(href)

                    name = item.get_attribute("aria-label") or ""
                    if not name:
                        name = item.inner_text().split("\n")[0].strip()
                    if not name:
                        continue

                    # Ambil teks kontainer induk untuk detail
                    parent = item.locator("xpath=..")
                    parent_lines = [l.strip() for l in parent.inner_text().split("\n") if l.strip()]

                    # Ekstraksi rating & reviews
                    rating, reviews = parse_rating_reviews(parent, parent_lines)

                    # Ekstraksi kategori dan alamat
                    category, address = parse_category_and_address(parent_lines)

                    # Ekstraksi koordinat
                    lat, lng = parse_coordinates_from_url(href)

                    # Cek aturan deduplikasi: HANYA skip jika Nama DAN Geolokasi SAMA
                    if check_is_duplicate(name, lat, lng, address):
                        logger.info(f"Deduplikasi: '{name}' di lokasi sama dilewati.")
                        continue

                    # Deteksi Kecamatan secara otomatis & presisi
                    district_name = job.district.strip() if job.district else ""
                    if not district_name:
                        # Coba deteksi dari teks alamat
                        addr_lower = (address or "").lower()
                        for d in ['Colomadu', 'Gondangrejo', 'Jaten', 'Jatipuro', 'Jatiyoso', 'Jenawi', 'Jumantono', 'Jumapolo', 'Karanganyar', 'Karangpandan', 'Kebakkramat', 'Kerjo', 'Matesih', 'Mojogedang', 'Ngargoyoso', 'Tasikmadu', 'Tawangmangu']:
                            if d.lower() in addr_lower:
                                district_name = d
                                break
                    if not district_name:
                        q_lower = (item_full_query or "").lower()
                        for d in ['Colomadu', 'Gondangrejo', 'Jaten', 'Jatipuro', 'Jatiyoso', 'Jenawi', 'Jumantono', 'Jumapolo', 'Karanganyar', 'Karangpandan', 'Kebakkramat', 'Kerjo', 'Matesih', 'Mojogedang', 'Ngargoyoso', 'Tasikmadu', 'Tawangmangu']:
                            if d.lower() in q_lower:
                                district_name = d
                                break
                    if not district_name:
                        district_name = "Kabupaten Karanganyar"

                    # Simpan ke database dengan kategori dan kecamatan yang pasti terisi
                    Place.objects.create(
                        job=job,
                        name=name,
                        category=category or cat_name,
                        district=district_name,
                        address=address,
                        rating=rating,
                        reviews_count=reviews,
                        google_maps_url=href,
                        latitude=lat,
                        longitude=lng,
                        search_query=item_full_query
                    )
                    scraped_count += 1
                    cat_scraped += 1
                    job.total_scraped = scraped_count
                    job.save(update_fields=['total_scraped'])

            browser.close()

        if is_job_cancelled(job_id):
            job.mark_cancelled(total=scraped_count)
            logger.info(f"Job {job_id} berhasil dihentikan atas permintaan pengguna ({scraped_count} tempat tersimpan).")
            return

        job.mark_completed(scraped_count)
        logger.info(f"Job {job_id} berhasil selesai dengan {scraped_count} tempat.")

    except Exception as e:
        logger.error(f"Error pada Playwright scraper untuk job {job_id}: {str(e)}", exc_info=True)
        job.mark_failed(str(e))
    finally:
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
