from flask import Flask, request, jsonify
import os
import requests
import math
import json

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_GROUP_ID = os.environ.get("ADMIN_GROUP_ID")

SHOP_LAT = 56.844628
SHOP_LON = 53.203414

carts = {}
orders = {}

# ===============================
# РАССТОЯНИЕ
# ===============================

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c


# ===============================
# ДОСТАВКА
# ===============================

@app.route("/delivery", methods=["POST"])
def delivery():

    data = request.json

    user_id = str(data["user_id"])

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
# ДОБАВИТЬ В КОРЗИНУ
# ===============================

@app.route("/add", methods=["POST"])
def add_to_cart():

    data = request.json

    user_id = str(data["user_id"])
    name = data["name"]
    price = int(data["price"])

    noodle = data.get("noodle","")
    sauce = data.get("sauce","")

    if noodle:
        name += f" | {noodle}"

    if sauce:
        name += f" | {sauce}"

    cart = carts.setdefault(user_id,{})

    if name in cart:
        cart[name]["qty"] += 1
    else:
        cart[name] = {
            "price": price,
            "qty": 1
        }

    return jsonify({"status":"added"})


# ===============================
# КОРЗИНА
# ===============================

@app.route("/cart/<user_id>", methods=["GET"])
def get_cart(user_id):

    cart = carts.get(user_id,{})

    total = 0
    text = ""

    for name,item in cart.items():

        subtotal = item["price"] * item["qty"]
        total += subtotal

        text += f"{name} x {item['qty']} — {subtotal} ₽\n"

    delivery_price = orders.get(user_id,{}).get("delivery_price",0)

    total += delivery_price

    text += f"\n🚚 Доставка: {delivery_price} ₽"

    return jsonify({
        "cart": text.strip(),
        "order_total": total
    })


# ===============================
# ОФОРМЛЕНИЕ ЗАКАЗА
# ===============================

@app.route("/checkout", methods=["POST"])
def checkout():

    data = request.json

    user_id = str(data["user_id"])
    receipt = data.get("receipt")

    cart = carts.get(user_id,{})
    order_data = orders.get(user_id)

    if not order_data:
        return jsonify({"status":"error"})

    total = 0

    text = "🆕 Новый заказ\n\n"

    for name,item in cart.items():

        subtotal = item["price"] * item["qty"]
        total += subtotal

        text += f"{name} x {item['qty']} — {subtotal} ₽\n"

    delivery_price = order_data["delivery_price"]

    total += delivery_price

    text += f"\n🚚 Доставка: {delivery_price} ₽"
    text += f"\n💰 ИТОГО: {total} ₽"
    text += f"\n📞 Телефон: {order_data['phone']}"
    text += f"\n📍 Зона: {order_data['zone']}"

    send_to_admin(
        text,
        user_id,
        receipt,
        order_data["lat"],
        order_data["lon"]
    )

    carts.pop(user_id,None)

    return jsonify({"status":"sent"})


# ===============================
# ОТПРАВКА АДМИНУ
# ===============================

def send_to_admin(text,user_id,receipt,lat,lon):

    keyboard = {
        "inline_keyboard":[[
            {"text":"✅ Одобрить","callback_data":f"approve_{user_id}"},
            {"text":"❌ Отклонить","callback_data":f"reject_{user_id}"}
        ]]
    }

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id":ADMIN_GROUP_ID,
            "text":text,
            "reply_markup":keyboard
        }
    )

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendLocation",
        json={
            "chat_id":ADMIN_GROUP_ID,
            "latitude":lat,
            "longitude":lon
        }
    )

    if receipt:

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            json={
                "chat_id":ADMIN_GROUP_ID,
                "photo":receipt,
                "caption":f"Чек оплаты\nID заказа: {user_id}"
            }
        )


# ===============================
# КНОПКИ АДМИНА
# ===============================

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():

    data = request.json

    if "callback_query" not in data:
        return {"ok":True}

    query = data["callback_query"]

    callback = query["data"]

    chat_id = query["message"]["chat"]["id"]
    message_id = query["message"]["message_id"]

    user_id = callback.split("_")[1]

    if callback.startswith("approve_"):

        keyboard = {
            "inline_keyboard":[[
                {"text":"🍳 Готовится","callback_data":f"cook_{user_id}"}
            ]]
        }

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup",
            json={
                "chat_id":chat_id,
                "message_id":message_id,
                "reply_markup":keyboard
            }
        )

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id":user_id,
                "text":"✅ Заказ подтвержден и готовится"
            }
        )


    elif callback.startswith("reject_"):

        keyboard = {
            "inline_keyboard":[[
                {"text":"❌ Заказ отклонен","callback_data":"done"}
            ]]
        }

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup",
            json={
                "chat_id":chat_id,
                "message_id":message_id,
                "reply_markup":keyboard
            }
        )

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id":user_id,
                "text":"❌ Заказ отклонен"
            }
        )


    elif callback.startswith("cook_"):

        keyboard = {
            "inline_keyboard":[[
                {"text":"🚗 Курьер выехал","callback_data":f"delivery_{user_id}"}
            ]]
        }

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup",
            json={
                "chat_id":chat_id,
                "message_id":message_id,
                "reply_markup":keyboard
            }
        )

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id":user_id,
                "text":"🍳 Ваш заказ готовится"
            }
        )


    elif callback.startswith("delivery_"):

        keyboard = {
            "inline_keyboard":[[
                {"text":"📦 Доставлено","callback_data":f"done_{user_id}"}
            ]]
        }

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup",
            json={
                "chat_id":chat_id,
                "message_id":message_id,
                "reply_markup":keyboard
            }
        )

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id":user_id,
                "text":"🚗 Курьер выехал к вам"
            }
        )


    elif callback.startswith("done_"):

        keyboard = {
            "inline_keyboard":[[
                {"text":"✅ Заказ завершен","callback_data":"done"}
            ]]
        }

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageReplyMarkup",
            json={
                "chat_id":chat_id,
                "message_id":message_id,
                "reply_markup":keyboard
            }
        )

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id":user_id,
                "text":"📦 Заказ доставлен. Спасибо!"
            }
        )

    return {"ok":True}


# ===============================
# ЗАПУСК
# ===============================

if __name__ == "__main__":

    port = int(os.environ.get("PORT",5000))

    app.run(host="0.0.0.0",port=port)
