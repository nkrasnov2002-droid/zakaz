from flask import Flask, request, jsonify

app = Flask(__name__)

# Хранилище корзин (в памяти)
carts = {}


# ============================
# ➕ ДОБАВИТЬ В КОРЗИНУ
# ============================
@app.route("/add", methods=["POST"])
def add_to_cart():
    data = request.json

    user_id = str(data["user_id"])
    name = data["name"]
    price = int(data["price"])

    if user_id not in carts:
        carts[user_id] = {}

    if name in carts[user_id]:
        carts[user_id][name]["qty"] += 1
    else:
        carts[user_id][name] = {
            "price": price,
            "qty": 1
        }

    return jsonify({"status": "ok"})


# ============================
# 🛒 ПОЛУЧИТЬ КОРЗИНУ
# ============================
@app.route("/cart/<user_id>", methods=["GET"])
def get_cart(user_id):
    cart = carts.get(user_id, {})

    total = 0
    items_text = ""

    for name, item in cart.items():
        qty = item["qty"]
        price = item["price"]
        subtotal = qty * price

        total += subtotal
        items_text += f"{name} x {qty} — {subtotal} ₽\n"

    if items_text == "":
        items_text = "пусто"

    return jsonify({
        "items": items_text.strip(),
        "total": total
    })


# ============================
# ❌ ОЧИСТИТЬ КОРЗИНУ
# ============================
@app.route("/clear/<user_id>", methods=["POST"])
def clear_cart(user_id):
    carts[user_id] = {}
    return jsonify({"status": "cleared"})
