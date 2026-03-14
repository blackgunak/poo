from django.db import models
import uuid
from django.contrib.auth import get_user_model

User = get_user_model()


class Film(models.Model):
    titre = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    duree = models.PositiveIntegerField(help_text='Durée en minutes')
    categorie = models.CharField(max_length=100, blank=True)
    affiche = models.ImageField(upload_to='affiches/', blank=True, null=True)
    date_sortie = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.titre


class Salle(models.Model):
    nom = models.CharField(max_length=100)
    nombre_rangees = models.PositiveIntegerField()
    nombre_places_par_rangee = models.PositiveIntegerField()

    def __str__(self):
        return self.nom


class Seance(models.Model):
    film = models.ForeignKey(Film, on_delete=models.CASCADE)
    salle = models.ForeignKey(Salle, on_delete=models.CASCADE)
    date = models.DateField()
    heure = models.TimeField()
    prix = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        ordering = ['date', 'heure']

    def __str__(self):
        return f"{self.film} - {self.date} {self.heure}"


class Place(models.Model):
    salle = models.ForeignKey(Salle, on_delete=models.CASCADE)
    rangee = models.PositiveIntegerField()
    numero = models.PositiveIntegerField()

    class Meta:
        unique_together = (('salle', 'rangee', 'numero'),)

    def __str__(self):
        return f"R{self.rangee}N{self.numero} ({self.salle})"


class Reservation(models.Model):
    STATUTS = (
        ('CONFIRMEE', 'Confirmée'),
        ('ANNULEE', 'Annulée'),
    )
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE)
    seance = models.ForeignKey(Seance, on_delete=models.CASCADE)
    date_reservation = models.DateTimeField(auto_now_add=True)
    montant_total = models.DecimalField(max_digits=8, decimal_places=2)
    statut = models.CharField(max_length=10, choices=STATUTS, default='CONFIRMEE')
    # QR code fields: single-use token
    qr_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    qr_valid = models.BooleanField(default=True)
    qr_created = models.DateTimeField(auto_now_add=True)
    qr_used_at = models.DateTimeField(null=True, blank=True)
    qr_used_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='used_qr_reservations')

    def __str__(self):
        return f"Reservation #{self.pk} - {self.utilisateur} - {self.seance}"


class Billet(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE, related_name='billets')
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    seance = models.ForeignKey(Seance, on_delete=models.CASCADE)

    class Meta:
        unique_together = (('place', 'seance'),)

    def save(self, *args, **kwargs):
        if not self.seance_id and self.reservation_id:
            self.seance = self.reservation.seance
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Billet {self.place} - {self.seance}"
