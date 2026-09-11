# 🗺️ Google Maps Pro Data Scraper (Python & Django)

Aplikasi web modern dan script CLI berbasis **Python & Django** untuk mengambil (scraping) data bisnis dari Google Maps—seperti restoran, cafe, rumah makan, toko, klinik, bengkel, hotel, dan jenis tempat lainnya. Data yang dikumpulkan meliputi **Nama Tempat, Kategori, Rating Bintang, Jumlah Ulasan, Alamat Lengkap, Nomor Telepon, Website, Link Google Maps, dan Koordinat GPS (Latitude/Longitude)** yang dapat langsung diekspor ke **Microsoft Excel (.xlsx)** dan **CSV**.

Aplikasi ini sudah siap untuk dijalankan di komputer lokal maupun di-**hosting** di cloud (VPS, Railway, Render, Docker).

---

## ✨ Fitur Utama

1. **Pencarian Spesifik hingga Tingkat Kecamatan**:
   - Mempersempit area scraping hingga ke level **Kecamatan** dan **Kota / Kabupaten** (misal: *"Cafe di Kecamatan Tebet, Jakarta Selatan"* atau *"Bengkel & Otomotif di Kecamatan Sukajadi, Bandung"*).
   - Terdapat **30 Kategori Bisnis Lengkap** yang dapat langsung dipilih dengan 1-klik (Cafe, Restoran, Sekolah, UMKM, Kedai, Hotel, Retail, Konveksi, Puskesmas, Bengkel, Salon, Apotek, Ekspedisi, Warteg & RM Padang, Notaris, dll.).
2. **Aturan Deduplikasi Cerdas (Aman untuk Cabang Bisnis)**:
   - Sistem **HANYA** menghapus/melewati data jika **Nama Tempat DAN Geolokasi (Latitude & Longitude) KEDUANYA SAMA**.
   - Jika namanya sama (misal *"Kopi Kenangan"* atau *"Alfamart"*) namun koordinat lokasinya berbeda, data **TETAP DISIMPAN** karena merupakan **cabang bisnis yang berbeda**.
3. **Dual Engine Scraping**:
   - 🤖 **Playwright Scraper (Headless Browser)**: Scraping otomatis langsung dari antarmuka Google Maps tanpa memerlukan API Key ataupun kartu kredit.
   - ⚡ **Google Places API (New) Resmi**: Opsi scraping menggunakan endpoint resmi Google Places API (`places:searchText`) untuk hasil instan dan terstruktur.
4. **Dashboard Web Interaktif (Django)**:
   - Antarmuka modern bertema dark-glassmorphic.
   - Kolom **Kecamatan** tersedia di tabel web dan form filter.
   - Live scraping monitor dengan progress bar real-time dan radar animation.
5. **Ekspor Data Sekali Klik**:
   - 📊 **Excel (.xlsx)**: File rapi dengan kolom Kecamatan, styling header, lebar kolom otomatis, dan link Google Maps aktif.
   - 📄 **CSV (.csv)**: Menggunakan encoding `UTF-8 with BOM` (`utf-8-sig`) agar kompatibel langsung di Microsoft Excel.
6. **Alat CLI Mandiri (`cli_scraper.py`)**:
   - Mendukung parameter `-q` (query), `-k` (kecamatan), `-c` (kota), `-l` (limit), dan `-o` (output).


---

## 📂 Struktur Direktori Proyek

```
d:/scraping/
├── config/                     # Konfigurasi Utama Django
│   ├── settings.py             # Settings (WhiteNoise, database, dsb)
│   ├── urls.py                 # Routing root
│   └── wsgi.py
├── scraper_app/                # Aplikasi Scraper
│   ├── models.py               # Database Place & ScrapeJob
│   ├── views.py                # Dashboard, API Polling, Export Excel/CSV
│   ├── scraper_service.py      # Engine Playwright & Places API
│   ├── export_service.py       # Pembuat file Excel (.xlsx) & CSV
│   ├── templates/scraper_app/  # Template HTML (base, index, job_detail)
│   └── static/scraper_app/     # CSS Modern & JavaScript Interaktif
├── cli_scraper.py              # Script Command Line untuk scraping via terminal
├── manage.py                   # CLI Django
├── requirements.txt            # Daftar dependensi Python
├── Dockerfile                  # Container Docker siap Chromium
├── docker-compose.yml          # Compose file untuk deploy cepat
├── Procfile                    # Siap deploy ke Railway / Render
└── README.md                   # Dokumentasi lengkap
```

---

## 🚀 Cara Menjalankan di Komputer Lokal (Windows / Mac / Linux)

### 1. Prasyarat
Pastikan Python 3.10+ sudah terinstal di komputer Anda.

### 2. Buat & Aktifkan Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / MacOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependensi & Browser Playwright
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Jalankan Migrasi Database
```bash
python manage.py migrate
```

### 5. Buat Akun Admin (Opsional)
```bash
python manage.py createsuperuser
```

### 6. Jalankan Web Server Django
```bash
python manage.py runserver
```
Buka browser dan akses: **http://127.0.0.1:8000**

---

## 🖥️ Menggunakan Script CLI (Tanpa Buka Web Server)

Jika Anda ingin scraping langsung dari Terminal / Command Prompt:

```bash
# Contoh 1: Ambil 30 cafe di Kemang Jakarta dan simpan ke Excel
python cli_scraper.py --query "Cafe di Kemang Jakarta" --limit 30 --output cafe_kemang.xlsx

# Contoh 2: Ambil 50 Rumah Makan Padang di Bandung dan simpan ke CSV
python cli_scraper.py --query "Rumah Makan Padang di Bandung" --limit 50 --output padang_bandung.csv

# Contoh 3: Buka jendela browser saat scraping (melihat prosesnya)
python cli_scraper.py --query "Restoran di Surabaya" --limit 20 --output restoran.xlsx --headful
```

---

## 🌐 Panduan Deployment / Hosting

### Opsi A: Deploy ke Railway / Render (Paling Mudah)
1. Push kode Anda ke repository GitHub.
2. Di **Railway** atau **Render**:
   - Hubungkan repository GitHub Anda.
   - Railway / Render akan mendeteksi `Dockerfile` secara otomatis.
   - Tambahkan Environment Variable:
     - `DJANGO_DEBUG`: `False`
     - `DJANGO_ALLOWED_HOSTS`: `*`
     - `DJANGO_SECRET_KEY`: *(isi string acak minimal 32 karakter)*
3. Aplikasi akan otomatis menginstal Chromium dan menjalankan server Gunicorn via port `$PORT`.

### Opsi B: Deploy ke VPS Ubuntu (DigitalOcean, AWS EC2, Linode, IDCloudHost, dll.)
1. Masuk ke VPS melalui SSH:
   ```bash
   sudo apt update && sudo apt install -y python3-pip python3-venv git
   ```
2. Clone repository dan siapkan environment:
   ```bash
   git clone <URL_REPO_ANDA> /var/www/gmaps_scraper
   cd /var/www/gmaps_scraper
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install --with-deps chromium
   ```
3. Jalankan migrasi dan collect static:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```
4. Jalankan menggunakan Gunicorn dan Systemd / Nginx:
   ```bash
   gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120
   ```

### Opsi C: Deploy dengan Docker Compose
```bash
docker compose up -d --build
```
Aplikasi akan langsung aktif di `http://IP_SERVER:8000`.

---

## 💡 Tips Pengambilan "Seluruh Data" di Google Maps
Google Maps membatasi tampilan hasil pencarian maksimal sekitar 20–120 tempat per satu kata kunci/area koordinat. Untuk mengumpulkan data dalam skala sangat besar di suatu kota atau provinsi:
- **Bagi berdasarkan area / kecamatan**: alih-alih hanya mencari *"Restoran Jakarta"*, lakukan pencarian per wilayah spesifik:
  - *"Restoran di Kebayoran Baru"*
  - *"Restoran di Senopati"*
  - *"Restoran di Tebet"*
  - *"Restoran di Kelapa Gading"*
- Sistem database di aplikasi ini otomatis mengaitkan data dengan query asal dan mencegah duplikasi ketika diekspor ke Excel!

---

## ⚖️ Kepatuhan & Informasi Google Maps Platform
Jika Anda memilih menggunakan **Engine 2 (Google Places API New)** dengan API Key:
- Penggunaan layanan Google Maps Platform dapat menimbulkan biaya pada billing account Google Cloud Anda setelah melampaui kuota gratis.
- Anda dapat membatasi penggunaan API Key melalui [Google Cloud Console API Keys Restriction](https://docs.cloud.google.com/api-keys/docs/add-restrictions-api-keys).
- Penggunaan tunduk pada [Google Maps Platform Terms of Service](https://cloud.google.com/maps-platform/terms).
