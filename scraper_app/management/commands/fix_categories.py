import re
from django.core.management.base import BaseCommand
from scraper_app.models import Place
from scraper_app.scraper_service import (
    clean_text_glyphs,
    is_operational_or_status,
    is_rating_review_text,
    is_likely_address,
    is_valid_category_candidate
)
from scraper_app.category_normalizer import (
    normalize_category,
    is_anomalous_category,
    extract_category_from_query
)


class Command(BaseCommand):
    help = 'Membersihkan anomali kategori (Rute, CVCWRC8, Tidak ada ulasan, bullet, ikon) dan menormalkan kategori sejenis'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Tampilkan simulasi perbaikan tanpa mengubah database'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        self.stdout.write(self.style.NOTICE(f"=== Memulai unifikasi dan pembersihan kategori {'(DRY RUN)' if dry_run else ''} ==="))

        total_inspected = 0
        total_fixed_cat = 0
        total_fixed_addr = 0
        reasons_count = {}

        places = Place.objects.all()

        for p in places.iterator():
            total_inspected += 1
            cat_orig = p.category or ""
            addr_orig = p.address or ""
            cat_clean = clean_text_glyphs(cat_orig).strip()
            addr_clean = clean_text_glyphs(addr_orig).strip()

            search_q = (p.search_query or (p.job.query if p.job else "")).strip()

            is_bad = is_anomalous_category(cat_clean) or not is_valid_category_candidate(cat_clean)
            candidate = ""
            need_addr_fix = False
            new_address = addr_clean

            if is_bad:
                # Klasifikasi alasan anomali
                cat_lower = cat_clean.lower()
                if cat_lower in ['rute', 'directions', 'situs web', 'website', 'simpan', 'bagikan']:
                    reason = 'tombol_ui_google'
                elif re.match(r'^[2-9A-Z]{4,8}\+?[2-9A-Z]{2,4}$', cat_clean, re.I) or (len(cat_clean) >= 5 and not any(v in cat_lower for v in ['a', 'i', 'u', 'e', 'o'])):
                    reason = 'plus_code_lokasi'
                elif 'tidak ada ulasan' in cat_lower or 'no reviews' in cat_lower:
                    reason = 'tidak_ada_ulasan'
                elif any(0xE000 <= ord(c) <= 0xF8FF for c in cat_orig):
                    reason = 'ikon_pua_glyph'
                elif 'bersponsor' in cat_lower:
                    reason = 'bersponsor'
                elif cat_clean in ['·', '•', '-', '.'] or len(cat_clean) <= 1:
                    reason = 'bullet_symbol'
                else:
                    reason = 'anomali_lainnya'
                reasons_count[reason] = reasons_count.get(reason, 0) + 1

                # Cek di kolom alamat apakah ada kategori tersasar
                if '·' in addr_clean or '•' in addr_clean:
                    parts = [clean_text_glyphs(x).strip() for x in re.split(r'[·•]', addr_clean) if clean_text_glyphs(x).strip()]
                    cat_parts = [x for x in parts if is_valid_category_candidate(x) and not is_anomalous_category(x)]
                    addr_parts = [x for x in parts if is_likely_address(x) or not is_valid_category_candidate(x)]
                    if cat_parts:
                        candidate = cat_parts[0]
                        new_address = ", ".join(addr_parts) if addr_parts else ""
                        need_addr_fix = True
                elif is_valid_category_candidate(addr_clean) and not is_likely_address(addr_clean) and not is_anomalous_category(addr_clean):
                    candidate = addr_clean
                    new_address = ""
                    need_addr_fix = True

                # Fallback ke kata kunci pencarian
                if not candidate and search_q:
                    candidate = extract_category_from_query(search_q)
            else:
                candidate = cat_clean

            # Terapkan Normalisasi Kategori (Satukan binatu/laundry, hotel, kafe, dsb)
            new_category = normalize_category(candidate, search_q)

            # Sanitasi Alamat jika masih memuat kategori atau harga
            if new_address:
                if '·' in new_address or '•' in new_address:
                    parts = [clean_text_glyphs(x).strip() for x in re.split(r'[·•]', new_address) if clean_text_glyphs(x).strip()]
                    addr_parts = [x for x in parts if is_likely_address(x) or not is_valid_category_candidate(x)]
                    clean_res = ", ".join(addr_parts)
                    if clean_res != new_address:
                        new_address = clean_res
                        need_addr_fix = True

                if re.search(r'^hotel\s+bintang\s+\d', new_address.lower()) or re.search(r'(?:rp\s*[\d\.]+|\/malam)', new_address.lower()):
                    new_address = ""
                    need_addr_fix = True

                if is_operational_or_status(new_address) or is_rating_review_text(new_address) or is_anomalous_category(new_address):
                    new_address = ""
                    need_addr_fix = True

            # Simpan jika ada perubahan kategori atau alamat
            if (new_category != cat_orig) or (new_address != addr_orig):
                if new_category != cat_orig:
                    total_fixed_cat += 1
                if new_address != addr_orig:
                    total_fixed_addr += 1

                if not dry_run:
                    p.category = new_category
                    p.address = new_address
                    p.save(update_fields=['category', 'address'])

        self.stdout.write(self.style.SUCCESS("\n[OK] Proses unifikasi dan pembersihan selesai!"))
        self.stdout.write(f"Total tempat diperiksa: {total_inspected}")
        self.stdout.write(self.style.SUCCESS(f"Total kategori disatukan & diperbaiki: {total_fixed_cat}"))
        self.stdout.write(self.style.SUCCESS(f"Total alamat dibersihkan: {total_fixed_addr}"))
        self.stdout.write("\nRincian anomali yang dipulihkan:")
        for r, cnt in sorted(reasons_count.items(), key=lambda x: -x[1]):
            self.stdout.write(f"  - {r}: {cnt} baris")
