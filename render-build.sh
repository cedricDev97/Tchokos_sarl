#!/usr/bin/env bash
# eKAKO V1 : préparation des dépendances et fichiers statiques.
# Les migrations s'exécutent séparément, via Render Pre-Deploy Command.
set -euo pipefail

python -m pip install -r requirements.txt
python manage.py check
python manage.py collectstatic --noinput
