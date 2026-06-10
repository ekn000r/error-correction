import json
import os
import uuid
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

ROOT = Path(__file__).resolve().parent
PRODUCTS_FILE = ROOT / "data" / "products.json"
UPLOADS_DIR = ROOT / "instance" / "uploads"
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024
UPLOADS_DIR.mkdir(exist_ok=True)


def read_products():
    return json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))


def write_products(products):
    PRODUCTS_FILE.write_text(json.dumps(products, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def save_upload(file):
    extension = Path(secure_filename(file.filename)).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        abort(400, description="Only JPG, PNG, WEBP, and GIF images are allowed")
    filename = f"{uuid.uuid4().hex}{extension}"
    file.save(UPLOADS_DIR / filename)
    return f"/uploads/{filename}"


def get_product_or_404(product_id):
    products = read_products()
    product = next((item for item in products if item["id"] == product_id), None)
    if not product:
        abort(404)
    return products, product


def require_admin():
    if request.args.get("admin") != ADMIN_KEY:
        abort(403)


def ensure_gallery_slots(product, count=6):
    gallery = product.setdefault("gallery", [])
    placeholder = product.get("image", "")
    while len(gallery) < count:
        gallery.append(placeholder)
    del gallery[count:]
    return gallery


def ensure_review_slots(product):
    count = product.get("reviewCount", 5)
    if count not in {5, 10, 15, 20}:
        count = 5
    product["reviewCount"] = count
    reviews = product.setdefault("reviews", [])
    placeholder = product.get("image", "")
    while len(reviews) < count:
        reviews.append({"image": placeholder, "name": "Customer", "instagram": ""})
    del reviews[count:]
    for review in reviews:
        review.setdefault("name", "Customer")
        review.setdefault("instagram", "")
        if not review.get("image") or not review["image"].startswith("/uploads/"):
            review["image"] = placeholder
    return reviews


def prepared_products():
    products = read_products()
    before = json.dumps(products, sort_keys=True)
    for product in products:
        ensure_gallery_slots(product)
        ensure_review_slots(product)
    if json.dumps(products, sort_keys=True) != before:
        write_products(products)
    return products


@app.get("/")
def home():
    return render_template("browsing.html")


@app.get("/<page>.html")
def page(page):
    if page not in {"browsing", "productview", "savedlist"}:
        abort(404)
    return render_template(f"{page}.html")


@app.get("/api/products")
def products():
    return jsonify(prepared_products())


@app.post("/api/products")
def create_product():
    require_admin()
    products = read_products()
    name = request.form.get("name", "").strip()
    price = request.form.get("price", "").strip()
    if not name or not price:
        return jsonify({"error": "Name and price are required"}), 400
    existing_images = [item.get("image", "") for item in products if item.get("image")]
    image = existing_images[len(products) % len(existing_images)] if existing_images else ""
    product = {
        "id": f"{secure_filename(name).lower() or 'product'}-{uuid.uuid4().hex[:6]}",
        "name": name,
        "price": price,
        "bought": max(0, request.form.get("bought", "0", type=int)),
        "bestSeller": False,
        "image": image,
        "alt": name,
        "reviewCount": 5,
    }
    ensure_gallery_slots(product)
    ensure_review_slots(product)
    products.append(product)
    write_products(products)
    return jsonify(product), 201


@app.delete("/api/products/<product_id>")
def delete_product(product_id):
    require_admin()
    products, product = get_product_or_404(product_id)
    for item in products:
        ensure_gallery_slots(item)
        ensure_review_slots(item)
    products.remove(product)
    write_products(products)
    return "", 204


@app.get("/api/admin-status")
def admin_status():
    return jsonify({"admin": request.args.get("admin") == ADMIN_KEY})


@app.put("/api/products/<product_id>")
def update_product(product_id):
    require_admin()
    products, product = get_product_or_404(product_id)

    for field in ("name", "price"):
        if field in request.form:
            value = request.form.get(field, "").strip()
            if not value:
                return jsonify({"error": f"{field} is required"}), 400
            product[field] = value

    if "bought" in request.form:
        product["bought"] = max(0, request.form.get("bought", "0", type=int))
    main_photo = request.files.get("mainPhoto")
    if main_photo and main_photo.filename:
        product["image"] = save_upload(main_photo)

    gallery_files = [file for file in request.files.getlist("galleryPhotos") if file.filename]
    if gallery_files:
        product["gallery"] = [save_upload(file) for file in gallery_files]

    product["alt"] = product["name"]
    write_products(products)
    return jsonify(product)


@app.put("/api/products/<product_id>/main-photo")
def update_main_photo(product_id):
    require_admin()
    products, product = get_product_or_404(product_id)
    photo = request.files.get("photo")
    if not photo or not photo.filename:
        abort(400, description="Photo is required")
    product["image"] = save_upload(photo)
    write_products(products)
    return jsonify(product)


@app.put("/api/products/<product_id>/gallery/<int:index>")
def gallery_photo(product_id, index):
    require_admin()
    products, product = get_product_or_404(product_id)
    gallery = ensure_gallery_slots(product)
    if index < 0 or index >= 6:
        abort(404)
    photo = request.files.get("photo")
    if not photo or not photo.filename:
        abort(400, description="Photo is required")
    gallery[index] = save_upload(photo)
    write_products(products)
    return jsonify(product)


@app.put("/api/products/<product_id>/review-count")
def set_review_count(product_id):
    require_admin()
    products, product = get_product_or_404(product_id)
    count = request.form.get("count", type=int)
    if count not in {5, 10, 15, 20}:
        abort(400, description="Review count must be 5, 10, 15, or 20")
    product["reviewCount"] = count
    ensure_review_slots(product)
    write_products(products)
    return jsonify(product)


@app.put("/api/products/<product_id>/reviews/<int:index>")
def review(product_id, index):
    require_admin()
    products, product = get_product_or_404(product_id)
    reviews = ensure_review_slots(product)
    if index < 0 or index >= len(reviews):
        abort(404)
    photo = request.files.get("photo")
    if photo and photo.filename:
        reviews[index]["image"] = save_upload(photo)
    reviews[index]["name"] = request.form.get("name", "").strip() or reviews[index].get("name", "Customer")
    reviews[index]["instagram"] = request.form.get("instagram", "").strip()
    write_products(products)
    return jsonify(product)


@app.get("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOADS_DIR, filename)


if __name__ == "__main__":
    app.run(debug=True)
