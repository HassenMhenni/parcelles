# Installation sur une machine neuve

De `git clone` à l'API qui répond. Testé sur Ubuntu 26.04 avec PostgreSQL 18 /
PostGIS 3.6 et Python 3.13.

Deux choses ne viennent pas avec le dépôt et doivent être faites à la main : le
fichier `.env` (il est dans `.gitignore`) et la base PostgreSQL. Tout le reste
est dans le dépôt, y compris `data/parcelles.csv` (3,3 Mo, 8 521 parcelles).

---

## 1. Les paquets système

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-dev \
                    gdal-bin libgdal-dev binutils \
                    postgresql postgresql-18-postgis-3
```

`18` doit correspondre à ta version majeure de PostgreSQL. Pour la connaître :

```bash
psql --version
```

`gdal-bin` et `libgdal-dev` sont indispensables : GeoDjango charge ces
bibliothèques au démarrage, sans elles Django refuse de se lancer.

---

## 2. La base et son utilisateur

```bash
sudo -u postgres psql -c "CREATE ROLE parcelles LOGIN SUPERUSER PASSWORD 'choisis-un-mot-de-passe';"
sudo -u postgres psql -c "CREATE DATABASE parcelles OWNER parcelles;"
```

`SUPERUSER` parce que `db/schema.sql` commence par `CREATE EXTENSION postgis`,
et seul un superutilisateur peut installer une extension. Acceptable sur une
machine de développement.

**Variante plus propre** : rôle sans `SUPERUSER`, et tu installes l'extension à
sa place. Le `CREATE EXTENSION IF NOT EXISTS` de `schema.sql` ne fera alors
rien.

```bash
sudo -u postgres psql -c "CREATE ROLE parcelles LOGIN PASSWORD 'choisis-un-mot-de-passe';"
sudo -u postgres psql -c "CREATE DATABASE parcelles OWNER parcelles;"
sudo -u postgres psql -d parcelles -c "CREATE EXTENSION postgis;"
```

Le rôle est propriétaire de la base : depuis PostgreSQL 15 cela suffit pour
qu'il puisse créer ses tables dans le schéma `public`.

---

## 3. Le projet et ses dépendances

```bash
git clone https://github.com/HassenMhenni/parcelles.git
cd parcelles

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Le fichier `.env`

Il contient le mot de passe de la base et la clé secrète, il est donc dans
`.gitignore` : **le `git clone` ne le ramène pas**. À écrire à la racine du
projet, à côté de `manage.py`.

```bash
cat > .env <<EOF
POSTGRES_DB=parcelles
POSTGRES_USER=parcelles
POSTGRES_PASSWORD=le-mot-de-passe-de-l-etape-2
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

DJANGO_DEBUG=1
DJANGO_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(50))")
DJANGO_ALLOWED_HOSTS=*
EOF
```

`POSTGRES_PASSWORD` doit être **exactement** celui du `CREATE ROLE` de l'étape 2.

---

## 5. Remplir la base

L'ordre compte.

```bash
python manage.py init_db          # extension + table parcelle + les 8 521 lignes du CSV
python manage.py migrate          # les tables de l'admin (comptes, sessions, logs)
python manage.py createsuperuser  # ton compte pour /admin
```

`init_db` applique `db/schema.sql` tel quel, puis charge `data/parcelles.csv`
par paquets de 1 000.

`migrate` ne touche jamais à la table `parcelle` — le modèle est
`managed = False` — il ne crée que les tables de Django.

---

## 6. Démarrer et vérifier

```bash
python manage.py runserver
```

Dans un autre terminal :

```bash
curl -s localhost:8000/health
# {"status":"ok","postgis":"3.6 USE_GEOS=1 USE_PROJ=1 USE_STATS=1","parcelles":8521}

curl -s 'localhost:8000/parcelles?section=AB&page_size=1'
```

Si `/health` répond ça, l'installation est terminée. L'admin est sur
<http://localhost:8000/admin/>, avec le compte créé à l'étape 5.

---

## Les fois suivantes

```bash
cd parcelles
source .venv/bin/activate
python manage.py runserver
```

---

## Pannes classiques

| Message | Cause | Solution |
|---|---|---|
| `Could not find the GDAL library` | `libgdal-dev` absent | étape 1 |
| `password authentication failed for user "parcelles"` | le `.env` ne correspond pas au `CREATE ROLE` | étape 4 |
| `The parcelle table already exists` | `init_db` relancé sur une base déjà remplie | `python manage.py init_db --reset` |
| `could not connect to server` | PostgreSQL arrêté | `sudo systemctl start postgresql` |

---

## Repartir d'une base propre

Vide la table `parcelle` et la recharge depuis le CSV. Les données créées via
l'API ou l'admin sont perdues.

```bash
python manage.py init_db --reset
```
