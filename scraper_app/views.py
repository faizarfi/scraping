import urllib.parse
import re
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Count, Avg
from django.utils import timezone
from django.contrib import messages
from .models import ScrapeJob, Place
from .scraper_service import start_scraping_async, request_cancel_job
from .export_service import generate_excel_bytes, generate_csv_bytes

def dashboard(request):
    """
    Halaman utama dashboard scraper: form pencarian, statistik, dan tabel tempat
    """
    search_q = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()
    sort_by = request.GET.get('sort', '-created_at')

    places = Place.objects.all()
    if search_q:
        places = places.filter(
            name__icontains=search_q
        ) | places.filter(
            address__icontains=search_q
        ) | places.filter(
            category__icontains=search_q
        ) | places.filter(
            district__icontains=search_q
        ) | places.filter(
            search_query__icontains=search_q
        )
    if category_filter:
        places = places.filter(category__icontains=category_filter)

    valid_sorts = {
        'newest': '-created_at',
        'oldest': 'created_at',
        'rating_desc': '-rating',
        'rating_asc': 'rating',
        'reviews_desc': '-reviews_count',
        'name_asc': 'name',
    }
    places = places.order_by(valid_sorts.get(sort_by, '-created_at'))

    # Pagination
    paginator = Paginator(places, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    # Statistics
    total_places = Place.objects.count()
    total_jobs = ScrapeJob.objects.count()
    avg_rating = Place.objects.filter(rating__isnull=False).aggregate(Avg('rating'))['rating__avg']
    top_categories = Place.objects.values('category').exclude(category="").annotate(count=Count('category')).order_by('-count')[:5]

    recent_jobs = ScrapeJob.objects.all()[:8]

    context = {
        'page_obj': page_obj,
        'total_places': total_places,
        'total_jobs': total_jobs,
        'avg_rating': round(avg_rating, 2) if avg_rating else 0.0,
        'top_categories': top_categories,
        'recent_jobs': recent_jobs,
        'search_q': search_q,
        'category_filter': category_filter,
        'sort_by': sort_by,
    }
    return render(request, 'scraper_app/index.html', context)


@require_POST
def start_scrape(request):
    """
    Endpoint untuk memulai proses scraping
    """
    query = request.POST.get('query', '').strip()
    location = request.POST.get('location', '').strip()
    district = request.POST.get('district', '').strip()
    engine = request.POST.get('engine', 'playwright')
    try:
        target_count = int(request.POST.get('target_count', 0))
    except (ValueError, TypeError):
        target_count = 0
    api_key = request.POST.get('api_key', '').strip()

    if not query:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Kata kunci pencarian tidak boleh kosong!'}, status=400)
        return redirect('dashboard')

    # Buat Job baru
    job = ScrapeJob.objects.create(
        query=query,
        location=location,
        district=district,
        engine=engine,
        target_count=target_count,
        status='pending'
    )

    # Jalankan background worker
    start_scraping_async(job.id, api_key=api_key if engine == 'places_api' else None)


    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'job_id': job.id,
            'query': job.query,
            'target': job.target_count,
            'engine': job.get_engine_display()
        })

    return redirect('job_detail', job_id=job.id)


def job_detail(request, job_id):
    """
    Halaman detail proses dan hasil scraping untuk job tertentu
    """
    job = get_object_or_404(ScrapeJob, id=job_id)
    places = job.places.all().order_by('-created_at')

    paginator = Paginator(places, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'job': job,
        'page_obj': page_obj,
    }
    return render(request, 'scraper_app/job_detail.html', context)


def job_status_api(request, job_id):
    """
    API JSON polling untuk memantau progres scraping secara real-time
    """
    try:
        job = ScrapeJob.objects.get(id=job_id)
        return JsonResponse({
            'status': job.status,
            'status_label': job.get_status_display(),
            'total_scraped': job.total_scraped,
            'target_count': job.target_count,
            'error_message': job.error_message,
            'completed_at': job.completed_at.strftime('%H:%M:%S') if job.completed_at else None
        })
    except ScrapeJob.DoesNotExist:
        return JsonResponse({'error': 'Job tidak ditemukan'}, status=404)


def export_excel(request):
    """
    Unduh data tempat ke format Microsoft Excel (.xlsx)
    """
    job_id = request.GET.get('job_id')
    search_q = request.GET.get('q', '').strip()

    if job_id:
        job = get_object_or_404(ScrapeJob, id=job_id)
        places = job.places.all().order_by('-created_at')
        safe_q = re.sub(r'[^\w\-]', '_', job.query[:25]).strip('_') or 'data'
        filename = f"google_maps_job_{job.id}_{safe_q}.xlsx"
    else:
        places = Place.objects.all()
        if search_q:
            places = places.filter(name__icontains=search_q) | places.filter(address__icontains=search_q)
        places = places.order_by('-created_at')
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"google_maps_semua_data_{timestamp}.xlsx"

    excel_bytes = generate_excel_bytes(places)
    response = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def export_csv(request):
    """
    Unduh data tempat ke format CSV (.csv) dengan UTF-8 BOM
    """
    job_id = request.GET.get('job_id')
    search_q = request.GET.get('q', '').strip()

    if job_id:
        job = get_object_or_404(ScrapeJob, id=job_id)
        places = job.places.all().order_by('-created_at')
        safe_q = re.sub(r'[^\w\-]', '_', job.query[:25]).strip('_') or 'data'
        filename = f"google_maps_job_{job.id}_{safe_q}.csv"
    else:
        places = Place.objects.all()
        if search_q:
            places = places.filter(name__icontains=search_q) | places.filter(address__icontains=search_q)
        places = places.order_by('-created_at')
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"google_maps_semua_data_{timestamp}.csv"

    csv_bytes = generate_csv_bytes(places)
    response = HttpResponse(csv_bytes, content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@require_POST
def delete_job(request, job_id):
    """
    Hapus job dan seluruh tempat yang terkait dengannya
    """
    job = get_object_or_404(ScrapeJob, id=job_id)
    query_text = job.query
    deleted_places_count = job.places.count()
    job.places.all().delete()
    job.delete()
    messages.success(request, f"Sesi scraping '{query_text}' dan {deleted_places_count} data tempat terkait berhasil dihapus.")
    return redirect('dashboard')


@require_POST
def cancel_job(request, job_id):
    """
    Hentikan proses scraping yang sedang berjalan.
    Mendukung permintaan via AJAX/Fetch dan Form POST.
    """
    job = get_object_or_404(ScrapeJob, id=job_id)
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'

    if job.status in ['pending', 'running']:
        request_cancel_job(job.id)
        msg = f"Scraping '{job.query}' berhasil dihentikan. {job.total_scraped} data tempat yang telah terkumpul tetap tersimpan."
        if is_ajax:
            return JsonResponse({
                'success': True,
                'message': msg,
                'job_id': job.id,
                'status': 'cancelled',
                'total_scraped': job.total_scraped
            })
        messages.info(request, msg)
    else:
        if is_ajax:
            return JsonResponse({
                'success': False,
                'message': f"Job sudah berstatus {job.get_status_display()}.",
                'job_id': job.id,
                'status': job.status
            })
        messages.warning(request, f"Job sudah berstatus {job.get_status_display()}.")

    return redirect(request.META.get('HTTP_REFERER') or 'dashboard')


@require_POST
def clear_all_data(request):
    """
    Hapus semua data tempat dan riwayat scraping agar database bersih,
    atau lakukan pembersihan duplikat saja.
    """
    scope = request.POST.get('scope', 'all')

    if scope == 'duplicates_only':
        # Smart Deduplication: Hapus hanya data tempat yang memiliki Nama + Geolokasi sama
        all_places = list(Place.objects.all().order_by('created_at'))
        seen = []
        duplicate_ids = []

        for p in all_places:
            is_dup = False
            name_clean = p.name.strip().lower()

            for s in seen:
                if name_clean == s['name']:
                    # Jika punya koordinat
                    if p.latitude is not None and p.longitude is not None and s['lat'] is not None and s['lng'] is not None:
                        if abs(p.latitude - s['lat']) < 0.00025 and abs(p.longitude - s['lng']) < 0.00025:
                            is_dup = True
                            break
                    # Fallback jika tanpa koordinat: cek kesamaan alamat
                    elif p.address and s['address'] and p.address.strip().lower() == s['address']:
                        is_dup = True
                        break

            if is_dup:
                duplicate_ids.append(p.id)
            else:
                seen.append({
                    'name': name_clean,
                    'lat': p.latitude,
                    'lng': p.longitude,
                    'address': p.address.strip().lower() if p.address else ""
                })

        if duplicate_ids:
            Place.objects.filter(id__in=duplicate_ids).delete()
            msg = f"Berhasil membersihkan {len(duplicate_ids)} data duplikat! Sisa data unik: {len(seen)} tempat."
        else:
            msg = "Tidak ditemukan data duplikat. Seluruh data tempat di database sudah unik."

        messages.info(request, msg)

    else:
        # Hapus seluruh tempat dan riwayat sesi
        total_places = Place.objects.count()
        total_jobs = ScrapeJob.objects.count()
        Place.objects.all().delete()
        ScrapeJob.objects.all().delete()
        messages.success(request, f"Database berhasil dikosongkan! {total_places} data tempat dan {total_jobs} riwayat sesi telah dihapus bersih.")

    return redirect('dashboard')

