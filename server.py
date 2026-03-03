from flask import Flask, request, jsonify
import os
import requests

app = Flask(__name__)

# ===============================
# 🔐 НАСТРОЙКИ
# ===============================

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # токен бота
ADMIN_GROUP_ID = os.environ.get("ADMIN_GROUP_ID")  # id группы админов

carts = {}
orders = {}

# ===============================
# ➕ ДОБАВИТЬ В КОРЗИНУ
# ===============================

@app.route("/add", methods=["POST"])
def add_to_cart():
    data = request.json

    user_id = str(data["user_id"])
    name = data["name"]
    price = int(data["price"])

    noodle = data.get("noodle")
    sauce = data.get("sauce")

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
# 📦 ОФОРМИТЬ ЗАКАЗ
# ===============================

@app.route("/checkout", methods=["POST"])
def checkout():
    data = request.json

    user_id = str(data["user_id"])
    payment = data.get("payment")
    receipt = data.get("receipt_file")

    cart = carts.get(user_id, {})

    if not cart:
        return jsonify({"status": "empty"})

    total = 0
    order_text = "🆕 Новый заказ\n\n"

    for name, item in cart.items():
        qty = item["qty"]
        price = item["price"]
        subtotal = qty * price
        total += subtotal
        order_text += f"{name} x {qty} — {subtotal} ₽\n"

    order_text += f"\n💰 ИТОГО: {total} ₽"
    order_text += f"\n💳 Оплата: {payment}"
    order_text += f"\n👤 ID клиента: {user_id}"

    orders[user_id] = {
        "status": "waiting"
    }

    send_to_admin(order_text, user_id, receipt)

    return jsonify({"status": "sent"})


# ===============================
# 📤 ОТПРАВКА В ГРУППУ
# ===============================

def send_to_admin(text, user_id, receipt):

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Одобрить", "callback_data": f"approve_{user_id}"},
                {"text": "❌ Отклонить", "callback_data": f"reject_{user_id}"}
            ]
        ]
    }

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": ADMIN_GROUP_ID,
            "text": text,
            "reply_markup": keyboard
        }
    )

    if receipt:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            json={
                "chat_id": ADMIN_GROUP_ID,
                "photo": receipt,
                "caption": f"Чек оплаты\nID: {user_id}"
            }
        )


# ===============================
# 🤖 WEBHOOK TELEGRAM
# ===============================

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    data = request.json

    if "callback_query" in data:
        query = data["callback_query"]
        action, user_id = query["data"].split("_")

        if action == "approve":
            send_to_user(user_id, "✅ Ваш заказ одобрен и передан в работу.")
            carts[user_id] = {}
            orders[user_id]["status"] = "approved"

        elif action == "reject":
            send_to_user(user_id, "❌ Заказ не оформлен. Проверьте оплату.")
            orders[user_id]["status"] = "rejected"

    return "ok"


# ===============================
# 📩 СООБЩЕНИЕ КЛИЕНТУ
# ===============================

def send_to_user(user_id, text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": user_id,
            "text": text
        }
    )


# ===============================
# 🚀 ЗАПУСК
# ===============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
