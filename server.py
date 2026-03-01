from flask import Flask, request, jsonify
import os

app = Flask(__name__)

# хранилище корзин пользователей
carts = {}

# ===============================
# ➕ ДОБАВИТЬ В КОРЗИНУ
# ===============================
@app.route("/add", methods=["POST"])
def add_to_cart():
    data = request.json

    user_id = str(data["user_id"])
    name = data["name"]
    price = int(data["price"])

    # новые параметры (необязательные)
    noodle = data.get("noodle")
    sauce = data.get("sauce")

    # если есть выбор лапши/соуса → добавляем к названию
    if noodle or sauce:
        options = ", ".join(filter(None, [noodle, sauce]))
        name = f"{name} ({options})"

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


# ===============================
# 🛒 ПОЛУЧИТЬ КОРЗИНУ
# ===============================
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


# ===============================
# ❌ ОЧИСТИТЬ КОРЗИНУ
# ===============================
@app.route("/clear/<user_id>", methods=["POST"])
def clear_cart(user_id):
    carts[user_id] = {}
    return jsonify({"status": "cleared"})


# ===============================
# 🚀 ЗАПУСК (ВАЖНО ДЛЯ RAILWAY)
# ===============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
