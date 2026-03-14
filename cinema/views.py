import json
from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.contrib.auth import login
from django.contrib.auth import logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.http import HttpResponseNotAllowed, HttpResponse, Http404
from django.urls import reverse
import qrcode
from io import BytesIO
from django.utils import timezone
from django.db.models import Sum, Count

from .models import Seance, Billet, Reservation, Place, Salle
from .forms import FilmForm, SalleForm
from .models import Film
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render
from django.views.decorators.http import require_http_methods



def index(request):
    seances = Seance.objects.select_related('film', 'salle').order_by('date', 'heure')
    featured = seances.first()
    films_affiche = (
        Film.objects.filter(seance__isnull=False)
        .distinct()
        .prefetch_related('seance_set__salle')
    )
    return render(
        request,
        'cinema/index.html',
        {
            'featured': featured,
            'films_affiche': films_affiche,
            'seances': seances[:20],
        },
    )


def seance_detail(request, pk):
    seance = get_object_or_404(Seance, pk=pk)
    # generate places for salle if none exist
    salle = seance.salle
    total = salle.nombre_rangees * salle.nombre_places_par_rangee
    # ensure places exist
    existing = Place.objects.filter(salle=salle).count()
    if existing < total:
        to_create = []
        for r in range(1, salle.nombre_rangees + 1):
            for n in range(1, salle.nombre_places_par_rangee + 1):
                to_create.append(Place(salle=salle, rangee=r, numero=n))
        # bulk create ignoring duplicates
        Place.objects.bulk_create(to_create, ignore_conflicts=True)

    # If client requests JSON configuration (used by seatmap.js)
    if request.GET.get('_format') == 'json':
        places = Place.objects.filter(salle=salle)
        place_map = {f"{p.rangee}-{p.numero}": p.id for p in places}
        return JsonResponse({
            'nombre_rangees': salle.nombre_rangees,
            'nombre_places_par_rangee': salle.nombre_places_par_rangee,
            'place_map': place_map,
        })

    autres_seances = (
        Seance.objects.filter(film=seance.film)
        .select_related('salle')
        .order_by('date', 'heure')
    )

    return render(
        request,
        'cinema/seance_detail.html',
        {
            'seance': seance,
            'autres_seances': autres_seances,
        },
    )


def seance_reserved_places(request, pk):
    seance = get_object_or_404(Seance, pk=pk)
    reserved = Billet.objects.filter(seance=seance).values_list('place_id', flat=True)
    return JsonResponse({'reserved': list(reserved)})


def create_reservation(request):
    # If user is not authenticated, return a clear JSON error (useful for AJAX)
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Vous devez être connecté·e pour réserver.'}, status=401)

    if request.method != 'POST':
        return HttpResponseBadRequest('POST required')
    try:
        data = json.loads(request.body.decode())
        seance_id = int(data.get('seance'))
        places = list(map(int, data.get('places', [])))
    except Exception:
        return HttpResponseBadRequest('Invalid JSON')

    seance = get_object_or_404(Seance, pk=seance_id)

    with transaction.atomic():
        # check availability
        existing = Billet.objects.select_for_update().filter(seance=seance, place_id__in=places)
        if existing.exists():
            return JsonResponse({'success': False, 'error': 'Certaines places ne sont plus disponibles.'}, status=409)

        montant = seance.prix * len(places)
        reservation = Reservation.objects.create(utilisateur=request.user, seance=seance, montant_total=montant)
        billets = []
        for pid in places:
            billets.append(Billet(reservation=reservation, place_id=pid, seance=seance))
        Billet.objects.bulk_create(billets)

    # build a URL where the QR will resolve to (scan endpoint)
    qr_scan_url = request.build_absolute_uri(reverse('cinema:qr_scan', args=[str(reservation.qr_token)]))
    reservation_url = request.build_absolute_uri(reverse('cinema:reservation_detail', args=[reservation.id]))
    return JsonResponse({'success': True, 'reservation_id': reservation.id, 'qr_scan_url': qr_scan_url, 'reservation_url': reservation_url})


@user_passes_test(lambda u: u.is_staff)
def dashboard_stats(request):
    total_reservations = Reservation.objects.count()
    recette_totale = Reservation.objects.aggregate(total=Sum('montant_total'))['total'] or 0
    seances_actives = Seance.objects.filter(date__gte=date.today()).count()
    # recette par séance
    recette_par_seance = (
        Reservation.objects.values('seance__id', 'seance__film__titre')
        .annotate(total=Sum('montant_total'))
        .order_by('-total')[:20]
    )
    # taux de remplissage par salle
    # simple salle rates computed per salle
    salles = []
    taux_sum = 0
    for salle in Salle.objects.all():
        capacite = salle.nombre_rangees * salle.nombre_places_par_rangee
        reserved = Billet.objects.filter(seance__salle=salle).count()
        taux = (reserved / capacite) * 100 if capacite else 0
        taux_sum += taux
        salles.append({'salle': salle.nom, 'capacite': capacite, 'reserved': reserved, 'taux': round(taux, 2)})

    taux_moyen = round((taux_sum / len(salles)), 2) if salles else 0

    reservations_par_jour = (
        Reservation.objects.extra(select={'jour': "date(date_reservation)"})
        .values('jour')
        .annotate(total=Count('id'))
        .order_by('jour')
    )

    return JsonResponse({
        'total_reservations': total_reservations,
        'recette_totale': float(recette_totale),
        'seances_actives': seances_actives,
        'taux_moyen_remplissage': taux_moyen,
        'recette_par_seance': list(recette_par_seance),
        'reservations_par_jour': [
            {
                'jour': str(item['jour']),
                'total': item['total'],
            }
            for item in reservations_par_jour
        ],
        'taux_salles': salles,
    })


@login_required
def dashboard(request):
    # Staff: existing admin dashboard
    if request.user.is_staff:
        return render(request, 'cinema/dashboard.html')

    # Regular user: show their reservations / billets
    reservations = (
        Reservation.objects.filter(utilisateur=request.user)
        .prefetch_related('billets__place', 'seance__film', 'seance__salle')
        .order_by('-date_reservation')
    )
    return render(request, 'cinema/user_dashboard.html', {'reservations': reservations})


@user_passes_test(lambda u: u.is_staff)
def reservation_list(request):
    # Staff view: list reservations with basic filters
    qs = (
        Reservation.objects.select_related('utilisateur', 'seance__film', 'seance__salle')
        .order_by('-date_reservation')
    )
    # simple optional filters
    statut = request.GET.get('statut')
    if statut == 'valid':
        qs = qs.filter(qr_valid=True)
    elif statut == 'used':
        qs = qs.filter(qr_valid=False)

    return render(request, 'cinema/reservations_list.html', {'reservations': qs, 'is_staff': request.user.is_staff})


@user_passes_test(lambda u: u.is_staff)
def reservation_qr_image_staff(request, pk):
    """Return PNG QR for staff (bypass owner check)."""
    reservation = get_object_or_404(Reservation, pk=pk)
    scan_url = request.build_absolute_uri(reverse('cinema:qr_scan', args=[str(reservation.qr_token)]))
    img_io = BytesIO()
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(scan_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return HttpResponse(img_io.getvalue(), content_type='image/png')


@user_passes_test(lambda u: u.is_staff)
def reservation_qr_download_staff(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    scan_url = request.build_absolute_uri(reverse('cinema:qr_scan', args=[str(reservation.qr_token)]))
    img_io = BytesIO()
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(scan_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(img_io, 'PNG')
    img_io.seek(0)
    response = HttpResponse(img_io.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="reservation_{reservation.id}_qr.png"'
    return response


@user_passes_test(lambda u: u.is_staff)
def reservation_scan_staff(request, token):
    """Scan token via AJAX for staff: returns JSON result and marks QR used."""
    try:
        reservation = Reservation.objects.get(qr_token=token)
    except Reservation.DoesNotExist:
        return JsonResponse({'status': 'notfound'})

    if not reservation.qr_valid:
        return JsonResponse({'status': 'used', 'reservation_id': reservation.id, 'used_at': reservation.qr_used_at.isoformat() if reservation.qr_used_at else None, 'used_by': str(reservation.qr_used_by) if reservation.qr_used_by else None})

    reservation.qr_valid = False
    reservation.qr_used_at = timezone.now()
    reservation.qr_used_by = request.user
    reservation.save()
    return JsonResponse({'status': 'ok', 'reservation_id': reservation.id, 'used_at': reservation.qr_used_at.isoformat(), 'used_by': str(request.user)})


@user_passes_test(lambda u: u.is_staff)
def film_list(request):
    films = Film.objects.prefetch_related('seance_set__salle').all()
    return render(request, 'cinema/films_list.html', {'films': films})


@user_passes_test(lambda u: u.is_staff)
def film_create(request):
    if request.method == 'POST':
        form = FilmForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('cinema:film_list')
    else:
        form = FilmForm()
    return render(request, 'cinema/films_form.html', {'form': form})


@user_passes_test(lambda u: u.is_staff)
def film_edit(request, pk):
    film = get_object_or_404(Film, pk=pk)
    if request.method == 'POST':
        form = FilmForm(request.POST, request.FILES, instance=film)
        if form.is_valid():
            form.save()
            return redirect('cinema:film_list')
    else:
        form = FilmForm(instance=film)
    return render(request, 'cinema/films_form.html', {'form': form, 'film': film})


@user_passes_test(lambda u: u.is_staff)
@require_http_methods(["POST", "GET"])
def film_delete(request, pk):
    film = get_object_or_404(Film, pk=pk)
    if request.method == 'POST':
        film.delete()
        return redirect('cinema:film_list')
    return render(request, 'cinema/films_confirm_delete.html', {'film': film})


@user_passes_test(lambda u: u.is_staff)
def salle_list(request):
    salles = Salle.objects.all()
    return render(request, 'cinema/salles_list.html', {'salles': salles})


@user_passes_test(lambda u: u.is_staff)
def salle_create(request):
    if request.method == 'POST':
        form = SalleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('cinema:salle_list')
    else:
        form = SalleForm()
    return render(request, 'cinema/salles_form.html', {'form': form})


@user_passes_test(lambda u: u.is_staff)
def salle_edit(request, pk):
    salle = get_object_or_404(Salle, pk=pk)
    if request.method == 'POST':
        form = SalleForm(request.POST, instance=salle)
        if form.is_valid():
            form.save()
            return redirect('cinema:salle_list')
    else:
        form = SalleForm(instance=salle)
    return render(request, 'cinema/salles_form.html', {'form': form, 'salle': salle})


@user_passes_test(lambda u: u.is_staff)
@require_http_methods(["POST", "GET"])
def salle_delete(request, pk):
    salle = get_object_or_404(Salle, pk=pk)
    if request.method == 'POST':
        salle.delete()
        return redirect('cinema:salle_list')
    return render(request, 'cinema/salles_confirm_delete.html', {'salle': salle})


def signup(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('cinema:index')
    else:
        form = UserCreationForm()
    return render(request, 'cinema/signup.html', {'form': form})


def logout_view(request):
    """Log out via POST only and show a confirmation message."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    logout(request)
    messages.success(request, 'Vous êtes déconnecté·e. À bientôt !')
    return redirect('cinema:index')


def reservation_qr_image(request, pk):
    # Return a PNG QR image for the reservation (only owner)
    reservation = get_object_or_404(Reservation, pk=pk)
    # allow owner or staff to view
    if reservation.utilisateur != request.user and not (request.user.is_authenticated and request.user.is_staff):
        return HttpResponse(status=403)

    # Encode the absolute scan URL into the QR
    scan_url = request.build_absolute_uri(reverse('cinema:qr_scan', args=[str(reservation.qr_token)]))

    img_io = BytesIO()
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(scan_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return HttpResponse(img_io.getvalue(), content_type='image/png')


def reservation_qr_download(request, pk):
    # Force download of the QR PNG for reservation owner
    reservation = get_object_or_404(Reservation, pk=pk)
    # allow owner or staff to download
    if reservation.utilisateur != request.user and not (request.user.is_authenticated and request.user.is_staff):
        return HttpResponse(status=403)

    scan_url = request.build_absolute_uri(reverse('cinema:qr_scan', args=[str(reservation.qr_token)]))

    img_io = BytesIO()
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(scan_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(img_io, 'PNG')
    img_io.seek(0)
    response = HttpResponse(img_io.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="reservation_{reservation.id}_qr.png"'
    return response


def reservation_detail(request, pk):
    reservation = get_object_or_404(Reservation, pk=pk)
    # allow owner or staff to view detail
    if reservation.utilisateur != request.user and not (request.user.is_authenticated and request.user.is_staff):
        return HttpResponse(status=403)
    return render(request, 'cinema/reservation_detail.html', {'reservation': reservation})


def qr_scan(request, token):
    # Scanning endpoint: single-use. Typical scanners open the URL via GET.
    try:
        reservation = Reservation.objects.get(qr_token=token)
    except Reservation.DoesNotExist:
        raise Http404('Code invalide')

    if not reservation.qr_valid:
        return render(request, 'cinema/qr_scan_result.html', {'status': 'used', 'reservation': reservation})

    # Mark as used and record time/operator
    reservation.qr_valid = False
    reservation.qr_used_at = timezone.now()
    reservation.qr_used_by = request.user if request.user.is_authenticated else None
    reservation.save()
    # optionally record usage time on reservation (reuse qr_created or add field)
    messages.success(request, 'QR scanné et marqué comme utilisé.')
    return render(request, 'cinema/qr_scan_result.html', {'status': 'ok', 'reservation': reservation})
