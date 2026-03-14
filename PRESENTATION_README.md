Générer la présentation PowerPoint (format académique)

Prérequis
- Python 3.8+
- Installer la dépendance `python-pptx` :

```bash
pip install python-pptx
```

Génération

```bash
python presentation_generate.py
```

Résultat
- Un fichier `Cinema_Presentation.pptx` sera créé dans le dossier courant.
- Si vous avez des images de démonstration (captures d'écran, affiches), placez-les dans `media/affiches/` pour qu'elles soient incluses automatiquement.

Personnalisation
- Modifiez `presentation_generate.py` pour ajuster le contenu des slides (titres, points, styles).

Questions / Suite
- Si tu veux que je génère directement le `.pptx` ici, je peux tenter de l'ajouter au repo si tu veux (mais il est plus simple d'exécuter le script localement).
