# Error Correction

A crochet product browsing website with a small Flask admin editor.

## Project structure

```text
app.py                 Flask application and API routes
data/products.json     Product catalog data
templates/             Website pages
static/                Public images and other assets
instance/uploads/      Admin-uploaded product images
```

## Run locally

```powershell
python -m pip install -r requirements.txt
$env:ADMIN_KEY="eknoor"
python app.py
```

Public view:

```text
http://127.0.0.1:5000/
```

Admin editing view:

```text
http://127.0.0.1:5000/?admin=eknoor
```

The admin view allows editing each product's photo URL, title, and price.
Use a private `ADMIN_KEY` before deploying publicly.

## Deploy on Render

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Environment variable: set `ADMIN_KEY` to a private value

Render's default filesystem is temporary. Attach a persistent disk before relying
on uploaded images or product edits in production.
