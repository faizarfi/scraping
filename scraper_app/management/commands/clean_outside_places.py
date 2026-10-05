import os
import shutil
from django.core.management.base import BaseCommand
from django.conf import settings
from scraper_app.models import Place, ScrapeJob
from scraper_app.geo_validator import (
    is_valid_karanganyar_place,
    resolve_karanganyar_district,
    check_coordinates_part
)


class Command(BaseCommand):
    help = 'Membersihkan data tempat yang berada di luar Kabupaten Karanganyar dan memvalidasi kecamatan yang benar'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulasikan proses pembersihan tanpa menghapus atau mengubah database'
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            default=True,
            help='Buat cadangan file sqlite sebelum melakukan pembersihan'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        do_backup = options.get('backup', True)

        self.stdout.write(self.style.NOTICE(
            f"=== Memulai Validasi & Pembersihan Wilayah Karanganyar {'(DRY RUN)' if dry_run else ''} ==="
        ))

        db_path = getattr(settings, 'DATABASES', {}).get('default', {}).get('NAME')
        if not dry_run and do_backup and db_path and os.path.exists(db_path):
            backup_path = f"{db_path}.backup_before_clean_outside"
            try:
                shutil.copyfile(db_path, backup_path)
                self.stdout.write(self.style.SUCCESS(f"Cadangan database berhasil dibuat di: {backup_path}"))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"Gagal membuat cadangan database: {e}"))

        total_inspected = 0
        outside_places = []
        updated_district_count = 0
        part1_colomadu = 0
        part2_main = 0

        places = Place.objects.all().order_by('id')
        for p in places.iterator():
            total_inspected += 1
            lat, lng = p.latitude, p.longitude
            addr = p.address or ""
            name = p.name or ""

            # Cek apakah berada di Karanganyar
            is_valid = is_valid_karanganyar_place(lat, lng, address=addr, name=name)

            if not is_valid:
                outside_places.append(p.id)
            else:
                part = check_coordinates_part(lat, lng)
                if part == 1:
                    part1_colomadu += 1
                elif part == 2:
                    part2_main += 1

                # Hitung kecamatan yang akurat
                correct_district = resolve_karanganyar_district(lat, lng, address=addr, query=p.search_query, target_district=p.district)
                if (p.district or "").strip() != correct_district:
                    if not dry_run:
                        Place.objects.filter(id=p.id).update(district=correct_district)
                    updated_district_count += 1

        total_outside = len(outside_places)
        self.stdout.write(f"Total tempat diperiksa: {total_inspected}")
        self.stdout.write(self.style.WARNING(f"Tempat di luar Karanganyar terdeteksi: {total_outside}"))
        self.stdout.write(self.style.SUCCESS(f"Tempat valid di Karanganyar: {total_inspected - total_outside}"))
        self.stdout.write(f"  - Wilayah Colomadu: {part1_colomadu}")
        self.stdout.write(f"  - Wilayah 16 Kecamatan Lainnya: {part2_main}")
        self.stdout.write(f"Kecamatan diperbarui: {updated_district_count}")

        if not dry_run and total_outside > 0:
            # Hapus dalam batch 1000 ID
            batch_size = 1000
            for i in range(0, total_outside, batch_size):
                batch_ids = outside_places[i:i + batch_size]
                Place.objects.filter(id__in=batch_ids).delete()
            self.stdout.write(self.style.SUCCESS(f"Berhasil menghapus {total_outside} data di luar Karanganyar dari database."))

            # Sinkronisasi total_scraped pada semua ScrapeJob
            for job in ScrapeJob.objects.all():
                real_count = job.places.count()
                if job.total_scraped != real_count:
                    job.total_scraped = real_count
                    job.save(update_fields=['total_scraped'])
            self.stdout.write(self.style.SUCCESS("Statistik ScrapeJob berhasil disinkronkan."))
        elif dry_run:
            self.stdout.write(self.style.NOTICE("Dry run selesai. Tidak ada data yang dihapus atau diubah."))
