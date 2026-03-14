from django.contrib import admin
from django.urls import path
from django.shortcuts import render
from django.utils import timezone
import re, uuid

from .models import Film, Salle, Seance, Place, Reservation, Billet


@admin.register(Film)
class FilmAdmin(admin.ModelAdmin):
    list_display = ('titre', 'categorie', 'date_sortie')


@admin.register(Salle)
class SalleAdmin(admin.ModelAdmin):
    list_display = ('nom', 'nombre_rangees', 'nombre_places_par_rangee')


@admin.register(Seance)
class SeanceAdmin(admin.ModelAdmin):
    list_display = ('film', 'salle', 'date', 'heure', 'prix')


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = ('salle', 'rangee', 'numero')


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'utilisateur', 'seance', 'date_reservation', 'montant_total', 'statut')
    change_list_template = 'admin/cinema/reservation/change_list.html'

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('scan/', self.admin_site.admin_view(self.scan_qr_view), name='cinema_reservation_scan'),
        ]
        return my_urls + urls

    def scan_qr_view(self, request):
        # Simple admin view to paste a token or URL and mark the reservation QR as used
        result = None
        # accept token via POST form or GET query param `token`
        token_or_url = ''
        if request.method == 'POST':
            token_or_url = request.POST.get('token_or_url', '').strip()
        else:
            token_or_url = request.GET.get('token', '') or ''
            token_or_url = token_or_url.strip()
            # if provided via GET, process immediately
            if token_or_url:
                pass
            m = re.search(r'([0-9a-fA-F\-]{32,36})', token_or_url)
            if m:
                token_str = m.group(1)
                try:
                    token_uuid = uuid.UUID(token_str)
                    try:
                        reservation = Reservation.objects.get(qr_token=token_uuid)
                        if not reservation.qr_valid:
                            result = {'status': 'used', 'reservation': reservation}
                        else:
                            reservation.qr_valid = False
                            reservation.qr_used_at = timezone.now()
                            reservation.qr_used_by = request.user
                            reservation.save()
                            result = {'status': 'ok', 'reservation': reservation}
                    except Reservation.DoesNotExist:
                        result = {'status': 'notfound'}
                except ValueError:
                    result = {'status': 'invalid'}
        if result is not None:
            return render(request, 'admin/cinema/reservation/scan_result.html', {'result': result})

        return render(request, 'admin/cinema/reservation/scan.html', {})


@admin.register(Billet)
class BilletAdmin(admin.ModelAdmin):
    list_display = ('reservation', 'place', 'seance')
