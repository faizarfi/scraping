from django.contrib import admin
from .models import ScrapeJob, Place

@admin.register(ScrapeJob)
class ScrapeJobAdmin(admin.ModelAdmin):
    list_display = ('query', 'location', 'engine', 'target_count', 'total_scraped', 'status', 'created_at')
    list_filter = ('status', 'engine', 'created_at')
    search_fields = ('query', 'location')
    readonly_fields = ('created_at', 'completed_at', 'total_scraped')

@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'rating', 'reviews_count', 'phone', 'address', 'search_query', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('name', 'address', 'category', 'search_query')
    readonly_fields = ('created_at',)
