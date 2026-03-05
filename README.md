# Billetterie Cinéma (Django)

Instructions pour démarrer le projet en développement.

1. Créez un environnement virtuel et installez les dépendances :

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

2. Configurez PostgreSQL si souhaité en exportant les variables d'environnement :

```
set DJ_DATABASE=postgres
set POSTGRES_DB=cinema
set POSTGRES_USER=postgres
set POSTGRES_PASSWORD=yourpw
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5432
```

3. Appliquez les migrations et créez un superuser :

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

4. Ouvrez http://127.0.0.1:8000/

Notes:
- Utiliser un vrai service de fichiers (MEDIA_ROOT) en production.
- Les images d'affiche nécessitent Pillow.
