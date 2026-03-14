from django.urls import path
from . import views

app_name = 'cinema'

urlpatterns = [
    # override auth logout to ensure POST handling and message
    path('accounts/logout/', views.logout_view, name='logout'),
    # Reservation QR endpoints
    path('reservation/<int:pk>/qrcode/image/', views.reservation_qr_image, name='reservation_qr_image'),
    path('reservation/<int:pk>/qrcode/download/', views.reservation_qr_download, name='reservation_qr_download'),
    path('reservation/<int:pk>/', views.reservation_detail, name='reservation_detail'),
    path('qr/<uuid:token>/', views.qr_scan, name='qr_scan'),
    path('', views.index, name='index'),
    path('seance/<int:pk>/', views.seance_detail, name='seance_detail'),
    path('seance/<int:pk>/places/', views.seance_reserved_places, name='seance_places'),
    path('reservation/create/', views.create_reservation, name='create_reservation'),
    path('dashboard/stats/', views.dashboard_stats, name='dashboard_stats'),
    path('signup/', views.signup, name='signup'),
    # Admin / CRUD
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/reservations/', views.reservation_list, name='reservation_list'),
    path('dashboard/reservations/<int:pk>/qrcode/image/', views.reservation_qr_image_staff, name='reservation_qr_image_staff'),
    path('dashboard/reservations/<int:pk>/qrcode/download/', views.reservation_qr_download_staff, name='reservation_qr_download_staff'),
    path('dashboard/reservations/scan/<uuid:token>/', views.reservation_scan_staff, name='reservation_scan_staff'),
    path('films/', views.film_list, name='film_list'),
    path('films/create/', views.film_create, name='film_create'),
    path('films/<int:pk>/edit/', views.film_edit, name='film_edit'),
    path('films/<int:pk>/delete/', views.film_delete, name='film_delete'),

    path('salles/', views.salle_list, name='salle_list'),
    path('salles/create/', views.salle_create, name='salle_create'),
    path('salles/<int:pk>/edit/', views.salle_edit, name='salle_edit'),
    path('salles/<int:pk>/delete/', views.salle_delete, name='salle_delete'),
]
