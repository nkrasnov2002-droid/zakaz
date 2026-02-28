from flask import Flask, request, jsonify

app = Flask(__name__)

# Хранилище корзин
carts = {}

# =========================
# ➕ ДОБАВИТЬ В КОРЗИНУ
# =========================
@app.route('/add', methods=['POST'])
def add_to_cart():
    data = request.json

    user_id = str(data.get('user_id'))
    name = data.get('name')
    price = int(data.get('price'))

    if not user_id or not name or not price:
        return jsonify({"error": "missing data"}), 400

    if user_id not in carts:
        carts[user_id] = {}

    if name in carts[user_id]:
        carts[user_id][name]['qty'] += 1
    else:
        carts[user_id][name] = {
            "price": price,
            "qty": 1
        }

    return jsonify({"status": "ok"})


# =========================
# 🛒 ПОЛУЧИТЬ КОРЗИНУ
# =========================
@app.route('/cart/<user_id>', methods=['GET'])
def get_cart(user_id):
    cart = carts.get(user_id, {})

    total = 0
    items_text = ""

    for name, data in cart.items():
        qty = data["qty"]
        price = data["price"]
        subtotal = qty * price
        total += subtotal

        items_text += f"{name} × {qty} — {subtotal} ₽\n"

    if items_text == "":
        items_text = "пусто"

    return jsonify({
        "items": items_text.strip(),
        "total": total
    })


# =========================
# ❌ ОЧИСТИТЬ КОРЗИНУ
# =========================
@app.route('/clear/<user_id>', methods=['POST'])
def clear_cart(user_id):
    carts[user_id] = {}
    return jsonify({"status": "cleared"})


# =========================
# 🚀 ЗАПУСК СЕРВЕРА
# =========================
if __name__ == '__main__':

    import os
port = int(os.environ.get("PORT", 5000))
app.run(host="0.0.0.0", port=port)
