from datetime import datetime, time
from decimal import Decimal

from django import forms

from .models import Film, Reservation, Salle, Seance


class FilmForm(forms.ModelForm):
    salle = forms.ModelChoiceField(
        queryset=Salle.objects.all(),
        required=True,
        label='Salle',
        help_text="Chaque film doit être lié à une salle.",
    )
    dates_visionnage = forms.CharField(
        required=True,
        label='Dates de visionnage',
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': '2026-03-01, 2026-03-05'}),
        help_text='Saisissez une ou plusieurs dates au format AAAA-MM-JJ, séparées par des virgules ou des retours à la ligne.',
    )

    class Meta:
        model = Film
        fields = ['titre', 'description', 'duree', 'categorie', 'affiche', 'date_sortie']
        widgets = {
            'date_sortie': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            seances = Seance.objects.filter(film=self.instance).order_by('date', 'heure')
            premiere_seance = seances.first()
            if premiere_seance:
                self.fields['salle'].initial = premiere_seance.salle
                dates_uniques = []
                seen = set()
                for seance in seances:
                    if seance.date not in seen:
                        seen.add(seance.date)
                        dates_uniques.append(seance.date.isoformat())
                self.fields['dates_visionnage'].initial = ', '.join(dates_uniques)

    def clean_dates_visionnage(self):
        brut = self.cleaned_data.get('dates_visionnage', '')
        morceaux = [p.strip() for p in brut.replace('\n', ',').split(',') if p.strip()]
        if not morceaux:
            raise forms.ValidationError('Ajoutez au moins une date de visionnage.')

        dates = []
        for morceau in morceaux:
            try:
                parsed = datetime.strptime(morceau, '%Y-%m-%d').date()
            except ValueError:
                raise forms.ValidationError(
                    f"Date invalide '{morceau}'. Utilisez le format AAAA-MM-JJ."
                )
            dates.append(parsed)

        return sorted(set(dates))

    def clean(self):
        cleaned_data = super().clean()
        salle = cleaned_data.get('salle')
        dates = cleaned_data.get('dates_visionnage')

        if salle is None:
            raise forms.ValidationError('Veuillez choisir une salle pour ce film.')
        if not dates:
            raise forms.ValidationError('Veuillez fournir au moins une date de visionnage.')

        if self.instance and self.instance.pk:
            has_reservations = Reservation.objects.filter(seance__film=self.instance).exists()
            if has_reservations:
                signatures_actuelles = {
                    (seance.salle_id, seance.date)
                    for seance in Seance.objects.filter(film=self.instance)
                }
                signatures_nouvelles = {(salle.id, d) for d in dates}
                if signatures_actuelles != signatures_nouvelles:
                    raise forms.ValidationError(
                        'Ce film a déjà des réservations. La salle et les dates de visionnage ne peuvent plus être modifiées.'
                    )

        return cleaned_data

    def save(self, commit=True):
        film = super().save(commit=commit)
        if not commit:
            return film

        salle = self.cleaned_data['salle']
        dates = self.cleaned_data['dates_visionnage']

        seances_film = Seance.objects.filter(film=film).order_by('date', 'heure')
        has_reservations = Reservation.objects.filter(seance__film=film).exists()

        if seances_film.exists():
            premiere = seances_film.first()
            heure_defaut = premiere.heure
            prix_defaut = premiere.prix
        else:
            heure_defaut = time(20, 0)
            prix_defaut = Decimal('10.00')

        if not has_reservations:
            Seance.objects.filter(film=film).delete()
            Seance.objects.bulk_create(
                [
                    Seance(
                        film=film,
                        salle=salle,
                        date=date_visionnage,
                        heure=heure_defaut,
                        prix=prix_defaut,
                    )
                    for date_visionnage in dates
                ]
            )
        else:
            for date_visionnage in dates:
                Seance.objects.get_or_create(
                    film=film,
                    salle=salle,
                    date=date_visionnage,
                    defaults={'heure': heure_defaut, 'prix': prix_defaut},
                )

        return film


class SalleForm(forms.ModelForm):
    class Meta:
        model = Salle
        fields = ['nom', 'nombre_rangees', 'nombre_places_par_rangee']
