<div align="center">

# 🌐 Google Maps Pro Scraper
### High-Performance Business Data Extraction & Lead Generation Platform

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Django Framework](https://img.shields.io/badge/Django-6.1+-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-2EAD33?style=for-the-badge&logo=playwright&logoColor=white)](https://playwright.dev)
[![Docker Ready](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![Export Format](https://img.shields.io/badge/Export-Excel%20%7C%20CSV-217346?style=for-the-badge&logo=microsoftexcel&logoColor=white)](https://microsoft.com)

<p align="center">
  A robust full-stack data scraping platform designed to extract public business listings from Google Maps at scale. Built with Django, Playwright headless automation, Pandas, and OpenPyXL.
</p>

[Key Features](#-key-features) •
[Architecture](#-architecture) •
[Getting Started](#-getting-started) •
[CLI Usage](#-cli-usage) •
[Docker & Deployment](#-deployment--production) •
[Excel Export](#-multi-sheet-excel-export)

---

</div>

## 📌 Overview

**Google Maps Pro Scraper** is an enterprise-grade data intelligence and web scraping application engineered to collect detailed business information directly from Google Maps. It addresses the challenges of dynamic infinite scrolling, bot mitigation, branch deduplication, and structured export formatting.

Whether you need 20 cafes or 3,000+ commercial vendors across multiple categories and districts, the scraper runs asynchronously in the background with real-time UI monitoring and instant Excel/CSV generation.

### 📋 Extracted Data Points
| Field | Description | Example |
| :--- | :--- | :--- |
| **Name** | Official business or place name | *Kenangan Heritage Cafe* |
| **Category** | Primary industry classification | *Coffee Shop / Restaurant* |
| **Sub-district** | Administrative district / Kecamatan | *Kebayoran Baru* |
| **Rating** | Star rating (1.0 - 5.0) | *4.8* |
| **Reviews Count** | Total public reviews count | *1,250* |
| **Full Address** | Complete physical street address | *Jl. Senopati No. 12, Jakarta Selatan* |
| **Phone Number** | Contact telephone or mobile number | *+62 812-3456-7890* |
| **Website URL** | Official company website or portal | *https://example.com* |
| **Maps URL** | Direct Google Maps pin link | *https://maps.google.com/?cid=...* |
| **GPS Coordinates** | High-precision Latitude & Longitude | *-6.229728, 106.807441* |
| **Search Query** | Keyword query used during discovery | *Cafe di Senopati* |
| **Timestamp** | Exact record discovery datetime | *2026-09-11 12:00:00* |

---

## ✨ Key Features

### 1. 🎯 Multi-Category Batch Scraping
- Select and scrape up to **30 business categories simultaneously** (or input custom keywords).
- Independent batch processing guarantees that each category is queried thoroughly without dividing or choking target limits.

### 2. ⚡ "Unlimited / To-The-End" Target Mode
- Supports both defined target numbers (e.g. 50, 100 per category) and **Unlimited Extraction Mode** (`value="0"`).
- Automatically triggers continuous dynamic mouse-wheel scrolling until Google Maps reaches the absolute end of the feed (*"You've reached the end of the list"*).

### 3. 🧠 Smart Deduplication Engine (Branch-Safe)
- Avoids false duplicate elimination: **Only skips records if BOTH the Name AND GPS Coordinates (Latitude/Longitude) are identical**.
- Preserves franchises and business branches (e.g., *Alfamart*, *Indomaret*, *Starbucks*) that share the same brand name but operate in different geographical locations.

### 4. 🛑 On-the-Fly Scraping Cancellation
- Stop ongoing scrape operations anytime with the **"Hentikan Scraping"** button on the live progress modal or job detail screen.
- Employs thread-safe registry flags and graceful browser termination (`browser.close()`).
- **Zero data loss**: All records collected prior to cancellation are safely retained and fully exportable.

### 5. 📊 Multi-Sheet Excel Engine with Auto-Categorization
- **Tab 1: `Semua Data`**: Contains 100% of all scraped records with dark executive header styling, cell borders, auto-adjusted column widths, and clickable hyperlinks.
- **Category Sub-sheets**: Automatically groups records into dedicated tabs based on their normalized categories (case-insensitive deduplication).
- **Fallback Tab (`Kategori Lainnya`)**: Keeps workbooks clean and responsive by neatly housing smaller micro-categories when working with large datasets.
- **CSV Export**: Encoded in UTF-8 with BOM (`utf-8-sig`) for immediate compatibility with Microsoft Excel worldwide.

### 6. 🎨 Modern Dark-Glassmorphic Dashboard
- Built with standard Vanilla CSS and pure JavaScript—no bulky CSS frameworks.
- Clean typography and icons powered by **Lucide Icons** (strictly emoji-free UI).
- Real-time radar scan animation and AJAX status polling.

---

## 🏗️ Architecture

```
d:/scraping/
├── config/                     # Django Application Configuration
│   ├── settings.py             # App settings, WhiteNoise, Security
│   ├── urls.py                 # Core routing
│   └── wsgi.py                 # WSGI production entrypoint
├── scraper_app/                # Main Application Module
│   ├── models.py               # ScrapeJob & Place database models
│   ├── views.py                # Dashboard, API polling, cancellation & export
│   ├── scraper_service.py      # Playwright browser engine & cancellation worker
│   ├── export_service.py       # Excel (.xlsx) & CSV generation service
│   ├── templates/scraper_app/  # HTML templates (Dark theme, responsive)
│   └── static/scraper_app/     # CSS styles & client-side interactions
├── cli_scraper.py              # Standalone CLI script for terminal power-users
├── Dockerfile                  # Container definition with Chromium binaries
├── docker-compose.yml          # Single-command Docker orchestration
├── Procfile                    # Production process definition
├── requirements.txt            # Python dependencies
└── manage.py                   # Django CLI tool
```

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10, 3.11, or 3.12**
- **Git**
- Google Chrome or Chromium (installed automatically via Playwright)

### Local Setup (Windows / macOS / Linux)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/faizarfi/scraping.git
   cd scraping
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows (PowerShell / CMD)
   python -m venv .venv
   .venv\Scripts\activate

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Python packages & Playwright browser:**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Run database migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Start the development server:**
   ```bash
   python manage.py runserver
   ```

6. Open your browser and navigate to:
   ```
   http://127.0.0.1:8000
   ```

---

## 🖥️ CLI Usage

If you prefer running scrapers from terminal environments, cron jobs, or automated pipelines without launching the web server, use `cli_scraper.py`:

```bash
# Example 1: Scrape 50 Coffee Shops in South Jakarta and export to Excel
python cli_scraper.py --query "Coffee Shop di Jakarta Selatan" --limit 50 --output coffee_shops.xlsx

# Example 2: Scrape Restaurants in Bandung and export to CSV
python cli_scraper.py --query "Restoran di Bandung" --limit 100 --output restaurants.csv

# Example 3: Run with a visible browser window (Headful debugging mode)
python cli_scraper.py --query "Hotel di Surabaya" --limit 30 --output hotels.xlsx --headful
```

### CLI Arguments
| Flag | Description | Default |
| :--- | :--- | :--- |
| `--query`, `-q` | Search phrase or keyword | *(Required)* |
| `--limit`, `-l` | Target number of places | `30` |
| `--output`, `-o`| Output filename (`.xlsx` or `.csv`) | `places.xlsx` |
| `--headful` | Launch visible browser window for observation | `False` |

---

## 🐳 Deployment & Production

### Option 1: Docker & Docker Compose (Recommended)
The repository includes a production-ready `Dockerfile` that packages Python 3.12, system libraries, and Playwright Chromium dependencies:

```bash
docker compose up -d --build
```
The application will be accessible immediately at `http://YOUR_SERVER_IP:8000`.

### Option 2: VPS Linux (Ubuntu / Debian / AlmaLinux)
1. **Connect via SSH and update packages:**
   ```bash
   sudo apt update && sudo apt install -y python3-pip python3-venv git curl
   ```
2. **Clone and configure environment:**
   ```bash
   git clone https://github.com/faizarfi/scraping.git /var/www/scraper
   cd /var/www/scraper
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install --with-deps chromium
   ```
3. **Migrate & collect static assets:**
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```
4. **Run using Gunicorn:**
   ```bash
   gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 180
   ```

### Option 3: Cloud Platforms (Railway / Render / Fly.io)
- Connect this repository to **Railway** or **Render**.
- The service will automatically detect the `Dockerfile` and configure Chromium.
- Set the following environment variables in your cloud dashboard:
  - `DJANGO_DEBUG` = `False`
  - `DJANGO_ALLOWED_HOSTS` = `*`
  - `DJANGO_SECRET_KEY` = `<your-secure-random-key>`

---

## 📊 Multi-Sheet Excel Export

When downloading data from multi-category scrapes, the generated `.xlsx` workbook automatically structures the information:

```
[ Workbook: google_maps_job_4.xlsx ]
├── 📑 Tab 1: "Semua Data"         --> 100% of all scraped places across all keywords
├── 📑 Tab 2: "Cafe"               --> Dedicated filtered sheet for Cafes
├── 📑 Tab 3: "Restoran"           --> Dedicated filtered sheet for Restaurants
├── 📑 Tab 4: "Hotel"              --> Dedicated filtered sheet for Hotels
├── ...                            --> Top categories with high volume
└── 📑 Tab N: "Kategori Lainnya"   --> Clean aggregation of smaller categories
```

**Formatting highlights:**
- Professional dark slate header fill (`#1E293B`) with white bold text.
- Clean thin grid borders (`#CBD5E1`).
- Auto-adjusted column widths preventing text truncation.
- Direct active hyperlinks for Google Maps URLs.

---

## 📄 License & Disclaimer

This project is intended strictly for educational, research, and data aggregation purposes under fair use. Please respect Google Maps terms of service and website rate limits when scraping public data.

Developed with precision by [faizarfi](https://github.com/faizarfi).
