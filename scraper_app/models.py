import re
from django.db import models
from django.utils import timezone

class ScrapeJob(models.Model):
    ENGINE_CHOICES = [
        ('playwright', 'Playwright Headless Scraper (Tanpa API Key)'),
        ('places_api', 'Google Places API (New)'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Menunggu'),
        ('running', 'Sedang Berjalan'),
        ('completed', 'Selesai'),
        ('failed', 'Gagal'),
        ('cancelled', 'Dibatalkan'),
    ]

    query = models.CharField(max_length=255, verbose_name="Kata Kunci / Pencarian")
    location = models.CharField(max_length=150, blank=True, default="", verbose_name="Kota / Lokasi")
    district = models.CharField(max_length=150, blank=True, default="", verbose_name="Kecamatan")
    engine = models.CharField(max_length=30, choices=ENGINE_CHOICES, default='playwright', verbose_name="Engine")
    target_count = models.PositiveIntegerField(default=30, verbose_name="Target Jumlah")
    total_scraped = models.PositiveIntegerField(default=0, verbose_name="Total Didapat")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Status")
    error_message = models.TextField(blank=True, default="", verbose_name="Pesan Error")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Waktu Mulai")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Waktu Selesai")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Scrape Job"
        verbose_name_plural = "Scrape Jobs"

    def __str__(self):
        return f"[{self.status.upper()}] {self.query} ({self.total_scraped} hasil)"

    def mark_completed(self, total):
        self.status = 'completed'
        self.total_scraped = total
        self.completed_at = timezone.now()
        self.save()

    def mark_failed(self, error):
        self.status = 'failed'
        self.error_message = str(error)
        self.completed_at = timezone.now()
        self.save()

    def mark_cancelled(self, total=None):
        self.status = 'cancelled'
        if total is not None:
            self.total_scraped = total
        self.completed_at = timezone.now()
        self.save()


class Place(models.Model):
    job = models.ForeignKey(ScrapeJob, on_delete=models.SET_NULL, null=True, blank=True, related_name='places')
    name = models.CharField(max_length=255, verbose_name="Nama Tempat")
    category = models.CharField(max_length=150, blank=True, default="", verbose_name="Kategori")
    district = models.CharField(max_length=150, blank=True, default="", verbose_name="Kecamatan")
    address = models.TextField(blank=True, default="", verbose_name="Alamat")
    phone = models.CharField(max_length=100, blank=True, default="", verbose_name="Nomor Telepon")
    website = models.URLField(max_length=1000, blank=True, default="", verbose_name="Website")
    rating = models.FloatField(null=True, blank=True, verbose_name="Rating")
    reviews_count = models.PositiveIntegerField(default=0, verbose_name="Jumlah Ulasan")
    google_maps_url = models.URLField(max_length=1500, blank=True, default="", verbose_name="Link Google Maps")
    latitude = models.FloatField(null=True, blank=True, verbose_name="Latitude")
    longitude = models.FloatField(null=True, blank=True, verbose_name="Longitude")
    search_query = models.CharField(max_length=255, blank=True, default="", verbose_name="Query Asal")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ditemukan Pada")


    class Meta:
        ordering = ['-created_at']
        verbose_name = "Tempat / Bisnis"
        verbose_name_plural = "Daftar Tempat"

    def __str__(self):
        return f"{self.name} - {self.category or 'Umum'}"

    @property
    def clean_wa_phone(self):
        """
        Format nomor telepon untuk link WhatsApp https://wa.me/62...
        Mendukung nomor awalan 08..., +62..., 628...
        """
        if not self.phone:
            return ""
        num = re.sub(r'[^\d]', '', str(self.phone))
        if num.startswith('08'):
            return '62' + num[1:]
        elif num.startswith('628'):
            return num
        elif len(num) >= 9 and num.startswith('8'):
            return '62' + num
        return ""

    @property
    def display_category(self):
        """
        Kembalikan nama kategori yang bersih dari teks status operasional ('Buka'/'Tutup')
        """
        cat = (self.category or "").strip()
        if cat and cat.lower() not in ['buka', 'tutup', 'open', 'closed'] and 'pukul' not in cat.lower():
            return cat
        if self.search_query:
            clean = re.split(r'\s+di\s+|\s+in\s+|,', self.search_query, flags=re.IGNORECASE)[0].strip()
            if clean and clean.lower() not in ['buka', 'tutup', 'open', 'closed']:
                return clean.title()
        return "Bisnis"

    @property
    def display_address(self):
        """
        Kembalikan alamat yang bersih dari teks status operasional
        """
        addr = (self.address or "").strip()
        if addr and addr.lower() not in ['buka', 'tutup', 'open', 'closed'] and 'tutup pukul' not in addr.lower() and 'buka pukul' not in addr.lower():
            return addr
        return "-"
