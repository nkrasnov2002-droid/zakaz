from flask import Flask, request, jsonify
import os
import requests
import math
import json

app = Flask(__name__)

# ===============================
# 🔐 НАСТРОЙКИ
# ===============================

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_GROUP_ID = os.environ.get("ADMIN_GROUP_ID")

SHOP_LAT = 56.844628
SHOP_LON = 53.203414

carts = {}
orders = {}

# ===============================
# 📏 РАССТОЯНИЕ
# ===============================

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

# ===============================
# 🚚 ДОСТАВКА
# ===============================

@app.route("/delivery", methods=["POST"])
def delivery():
    data = request.json

    user_id = str(data["user_id"])
    
    import json

    coords = json.loads(data["lat"])
    
    lat = float(coords["latitude"])
    lon = float(coords["longitude"])

    phone = data["phone"]

    distance = calculate_distance(SHOP_LAT, SHOP_LON, lat, lon)

    if distance <= 5:
        zone = "🟢 Зеленая зона"
        price = 0
        time = "55 минут"
    elif distance <= 10:
        zone = "🔵 Голубая зона"
        price = 0
        time = "1.5 часа"
    else:
        zone = "🟣 Фиолетовая зона"
        price = 1000
        time = "2.5 часа"

    orders[user_id] = {
        "delivery_price": price,
        "delivery_time": time,
        "zone": zone,
        "lat": lat,
        "lon": lon,
        "phone": phone
    }

    return jsonify({
        "zone": zone,
        "delivery_price": price,
        "delivery_time": time
    })

# ===============================
# ➕ ДОБАВЛЕНИЕ В КОРЗИНУ
# ===============================

@app.route("/add", methods=["POST"])
def add_to_cart():
    data = request.json or {}

    user_id = str(data.get("user_id"))
    base_name = data.get("name")
    price = data.get("price")

    if not user_id or not base_name or not price:
        return jsonify({"status": "error", "message": "invalid data"}), 400

    price = int(price)

    noodle = data.get("noodle", "")
    sauce = data.get("sauce", "")

    name = base_name
    if noodle:
        name += f" | {noodle}"
    if sauce:
        name += f" | {sauce}"

    cart = carts.setdefault(user_id, {})

    if name in cart:
        cart[name]["qty"] += 1
    else:
        cart[name] = {
            "price": price,
            "qty": 1
        }

    return jsonify({"status": "added"})

# ===============================
# 🛒 КОРЗИНА
# ===============================

@app.route("/cart/<user_id>", methods=["GET"])
def get_cart(user_id):
    cart = carts.get(user_id, {})

    total = 0
    items_text = ""

    for name, item in cart.items():
        subtotal = item["price"] * item["qty"]
        total += subtotal
        items_text += f"{name} x {item['qty']} — {subtotal} ₽\n"

    delivery_price = orders.get(user_id, {}).get("delivery_price", 0)
    total += delivery_price

    items_text += f"\n🚚 Доставка: {delivery_price} ₽"

    return jsonify({
        "cart": items_text.strip(),
        "order_total": total
    })

# ===============================
# 📦 ОФОРМЛЕНИЕ
# ===============================

@app.route("/checkout", methods=["POST"])
def checkout():

    data = request.json or {}

    user_id = str(data.get("user_id"))
    receipt = data.get("receipt") or data.get("receipt_file")

    cart = carts.get(user_id, {})
    order_data = orders.get(user_id)

    if not order_data:
        return jsonify({"status": "error", "message": "no delivery data"})

    total = 0
    text = "🆕 Новый заказ\n\n"

    for name, item in cart.items():
        subtotal = item["price"] * item["qty"]
        total += subtotal
        text += f"{name} x {item['qty']} — {subtotal} ₽\n"

    delivery_price = order_data["delivery_price"]
    total += delivery_price

    text += f"\n🚚 Доставка: {delivery_price} ₽"
    text += f"\n💰 ИТОГО: {total} ₽"
    text += f"\n📞 Телефон: {order_data['phone']}"
    text += f"\n📍 Зона: {order_data['zone']}"

    try:
        print("SENDING ORDER")
        
        send_to_admin(
            text,
            user_id,
            receipt,
            float(order_data["lat"]),
            float(order_data["lon"])
        )
    except Exception as e:
        print("CHECKOUT ERROR:", e)

    carts.pop(user_id, None)

    return jsonify({"status": "sent"})

def send_to_admin(text, user_id, receipt, lat, lon):

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Одобрить", "callback_data": f"approve_{user_id}"},
            {"text": "❌ Отклонить", "callback_data": f"reject_{user_id}"}
        ]]
    }

    # сообщение
    r1 = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": ADMIN_GROUP_ID,
            "text": text,
            "reply_markup": keyboard
        }
    )

    print("SEND MESSAGE:", r1.text)

    # локация
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendLocation",
        json={
            "chat_id": ADMIN_GROUP_ID,
            "latitude": lat,
            "longitude": lon
        }
    )

    # чек
    if receipt:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            json={
                "chat_id": ADMIN_GROUP_ID,
                "photo": receipt,
                "caption": f"Чек оплаты\nID заказа: {user_id}"
            }
        )
        
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    data = request.json

    if "callback_query" in data:

        query = data["callback_query"]
        callback_data = query["data"]
        chat_id = query["message"]["chat"]["id"]
        message_id = query["message"]["message_id"]
        user_id = query["from"]["id"]

        # ОДОБРИТЬ
        if callback_data.startswith("approve_"):

            order_user = callback_data.split("_")[1]

            keyboard = {
                "inline_keyboard": [[
                    {"text": "✅ Заказ одобрен", "callback_data": "done"}
                ]]
            }

            # меняем кнопки
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": keyboard
                }
            )

            # сообщение клиенту
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": order_user,
                    "text": "✅ Ваш заказ подтвержден и готовится!"
                }
            )

        # ОТКЛОНИТЬ
        if callback_data.startswith("reject_"):

            order_user = callback_data.split("_")[1]

            keyboard = {
                "inline_keyboard": [[
                    {"text": "❌ Заказ отклонен", "callback_data": "done"}
                ]]
            }

            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "reply_markup": keyboard
                }
            )

            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": order_user,
                    "text": "❌ К сожалению, заказ не принят."
                }
            )

    return {"ok": True}

import time

last_update = 0

def check_callbacks():
    global last_update

    while True:

        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={"offset": last_update + 1}
        ).json()

        for update in r.get("result",[]):

            last_update = update["update_id"]

            if "callback_query" in update:

                callback = update["callback_query"]
                data = callback["data"]

                if data.startswith("approve_"):

                    user_id = data.split("_")[1]

                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": user_id,
                            "text": "✅ Ваш заказ подтвержден!"
                        }
                    )

                if data.startswith("reject_"):

                    user_id = data.split("_")[1]

                    requests.post(
                        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                        json={
                            "chat_id": user_id,
                            "text": "❌ Заказ отклонен"
                        }
                    )

        time.sleep(2)
        
# ===============================
# 🚀 ЗАПУСК
# ===============================
import threading

threading.Thread(target=check_callbacks).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


























