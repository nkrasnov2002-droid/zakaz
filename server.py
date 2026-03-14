from flask import Flask, request, jsonify
import os
import requests
import math
import json
import time
import threading

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_GROUP_ID = os.environ.get("ADMIN_GROUP_ID")

SERVER_URL = "https://zakaz-production-5164.up.railway.app"

SHOP_LAT = 56.844628
SHOP_LON = 53.203414

carts = {}
orders = {}
order_counter = 100

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
    address = "Ижевск, " + data["address"]
    phone = data["phone"]

    # Геокодирование через Яндекс
    geo = requests.get(
        "https://geocode-maps.yandex.ru/1.x/",
        params={
        "apikey": "0a901ccb-3f80-42b2-9304-23cd981df90c",
        "format": "json",
        "geocode": address,
        "kind": "house"
    }
).json()

    try:
        members = geo["response"]["GeoObjectCollection"]["featureMember"]

        # если адрес не найден
        if not members:
        return jsonify({
            "status": "error",
            "message": "❌ Адрес не найден. Проверьте правильность написания."
        })

        geo_object = members[0]["GeoObject"]

        pos = geo_object["Point"]["pos"]
        lon, lat = map(float, pos.split())

    # проверка что адрес именно в Ижевске
    full_address = geo_object["metaDataProperty"]["GeocoderMetaData"]["text"]

    if "Ижевск" not in full_address:
        return jsonify({
            "status": "error",
            "message": "❌ Мы доставляем только по Ижевску."
        })

    except:
        return jsonify({
        "status": "error",
        "message": "❌ Не удалось определить адрес. Напишите адрес точнее."
    })

    distance = calculate_distance(SHOP_LAT, SHOP_LON, lat, lon) * 2

    if distance <= 5:
        zone = "green"
        price = 0
        delivery_time = "55 минут"

    elif distance <= 10:
        zone = "blue"
        price = 0
        delivery_time = "1.5 часа"

    else:
        zone = "purple"
        price = 1000
        delivery_time = "2.5 часа"

    orders[user_id] = {
        "delivery_price": price,
        "delivery_time": delivery_time,
        "zone": zone,
        "lat": lat,
        "lon": lon,
        "phone": phone,
        "address": data["address"],
        "created_at": time.time()
    }

    return jsonify({
        "delivery_price": price,
        "delivery_time": delivery_time
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

@app.route("/set_pickup", methods=["POST"])
def set_pickup():

    data = request.json
    user_id = str(data["user_id"])

    orders.setdefault(user_id, {})
    orders[user_id]["delivery_type"] = "pickup"
    orders[user_id]["delivery_price"] = 0

    return jsonify({"status": "ok"})

# ===============================
# КОРЗИНА
# ===============================

@app.route("/cart/<user_id>", methods=["GET"])
def get_cart(user_id):

    cart = carts.get(user_id,{})

    total = 0
    text = ""

    i = 1
    index_map = {}

    for name,item in cart.items():

        subtotal = item["price"] * item["qty"]
        total += subtotal

        text += f"{i}. {name} x {item['qty']} - {subtotal} ₽\n"

        index_map[str(i)] = name
        i += 1
    
    orders.setdefault(user_id, {})
    orders[user_id]["index_map"] = index_map

    delivery_price = orders.get(user_id, {}).get("delivery_price", 0)

    delivery_type = orders.get(user_id, {}).get("delivery_type", "delivery")

    discount = 0

    if delivery_type == "pickup":
        discount = int(total * 0.10)
        total -= discount
        text += f"\n🎁 Скидка самовывоза: -{discount} ₽"

    total += delivery_price

    text += f"\n🚚 Доставка: {delivery_price} ₽"

    return jsonify({
    "cart": text.strip(),
    "order_total": total
})
    
@app.route("/select_item", methods=["POST"])
def select_item():

    data = request.json

    user_id = str(data["user_id"])
    index = data["index"]

    index_map = orders.get(user_id, {}).get("index_map", {})

    if index not in index_map:
        return jsonify({"status":"error"})

    item_name = index_map[index]

    return jsonify({
        "item_name": item_name
    })

# ===============================
# ИЗМЕНЕНИЕ КОЛИЧЕСТВА ТОВАРА
# ===============================

@app.route("/change_quantity", methods=["POST"])
def change_quantity():

    data = request.json

    user_id = str(data["user_id"])
    item_name = data["item"]
    action = data["action"]

    cart = carts.get(user_id, {})

    if item_name not in cart:
        return jsonify({"status":"error"})

    if action == "plus":
        cart[item_name]["qty"] += 1

    elif action == "minus":

        cart[item_name]["qty"] -= 1

        if cart[item_name]["qty"] <= 0:
            del cart[item_name]

    elif action == "delete":

        del cart[item_name]

    return jsonify({"status":"ok"})
    
# ===============================
# ОЧИСТКА КОРЗИНЫ
# ===============================

@app.route("/clear/<user_id>", methods=["POST","GET"])
def clear_cart(user_id):

    user_id = str(user_id)

    carts.pop(user_id, None)
    orders.pop(user_id, None)

    return jsonify({
        "status": "cleared"
    })
    
# ===============================
# ОФОРМЛЕНИЕ ЗАКАЗА
# ===============================

@app.route("/checkout", methods=["POST"])
def checkout():

    global order_counter
    order_counter += 1
    order_number = order_counter
    
    data = request.json

    user_id = str(data["user_id"])
    receipt = data.get("receipt_file")

    cart = carts.get(user_id,{})
    order_data = orders.get(user_id)

    if not order_data:
        return jsonify({"status":"error"})

    total = 0

    text = f"🍣 Заказ №{order_number}\n\n"

    for name,item in cart.items():

        subtotal = item["price"] * item["qty"]
        total += subtotal

        text += f"{name} x {item['qty']} — {subtotal} ₽\n"
        
    delivery_price = order_data.get("delivery_price", 0)
    delivery_type = order_data.get("delivery_type","delivery")
    
    delivery_time = order_data.get("delivery_time", "не указано")

    if delivery_type == "pickup":
        text += "\n🏃 Самовывоз"
    else:
        text += f"\n🚚 Доставка: {delivery_price} ₽"

    text += f"\n💰 ИТОГО: {total} ₽"
    text += f"\n📞 Телефон: {order_data['phone']}"
    text += f"\n📍 Адрес: {order_data.get('address','Самовывоз')}"
    
    send_to_admin(
    text,
    user_id,
    receipt,
    delivery_time,
)
    carts.pop(user_id,None)

    return jsonify({"status":"sent"})


# ===============================
# ОТПРАВКА АДМИНУ
# ===============================

def send_to_admin(text, user_id, receipt_file, delivery_time):

    keyboard = {
        "inline_keyboard":[[
            {
                "text":"✅ Одобрить",
                "url":f"{SERVER_URL}/approve/{user_id}"
            },
            {
                "text":"❌ Отклонить",
                "url":f"{SERVER_URL}/reject/{user_id}"
            }
        ]]
    }

    if receipt_file:

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": ADMIN_GROUP_ID,
                "photo": receipt_file,
                "caption": text,
                "reply_markup": json.dumps(keyboard)
            }
        )

    else:

        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": ADMIN_GROUP_ID,
                "text": text + f"\n⏱ Время доставки: {delivery_time}",,
                "reply_markup": keyboard
            }
        )

# ===============================
# ОДОБРЕНИЕ ЗАКАЗА
# ===============================

@app.route("/approve/<user_id>")
def approve(user_id):

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id":user_id,
            "text":"✅ Ваш заказ подтвержден и готовится!"
        }
    )

    return "OK"


# ===============================
# ОТКЛОНЕНИЕ ЗАКАЗА
# ===============================

@app.route("/reject/<user_id>")
def reject(user_id):

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id":user_id,
            "text":"❌ К сожалению заказ отклонен."
        }
    )

    return "OK"

def cleanup_orders():

    now = time.time()

    for user_id in list(orders.keys()):

        created = orders[user_id].get("created_at", now)

        if now - created > 7200:  # 2 часа

            carts.pop(user_id, None)
            orders.pop(user_id, None)

            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": "⏳ Сессия заказа истекла.\n\nНажмите /start чтобы начать новый заказ."
                }
            )
def cleaner_loop():
    while True:
        cleanup_orders()
        time.sleep(300)  # проверка каждые 5 минут

threading.Thread(target=cleaner_loop, daemon=True).start()
# ===============================
# ЗАПУСК
# ===============================

if __name__ == "__main__":

    port = int(os.environ.get("PORT",5000))

    app.run(host="0.0.0.0",port=port)



























