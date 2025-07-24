import os
import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from flask import Flask, request

app = Flask(__name__)
PORT = int(os.environ.get('PORT', 8080))
bot = telebot.TeleBot(os.environ['TG_TOKEN'])

# MongoDB setup (for Koyeb: get connection string from Koyeb Secrets/Environment)
mongo_uri = os.environ['MONGO_URI']
client = MongoClient(mongo_uri)
db = client.get_database('telegram_subscriptions')
users = db.users
orders = db.orders

# --- Bot Handlers ---

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "🌟 Welcome to Premium Subscriptions! Send me your order (e.g., 'Hotstar Super 1 year').")

@bot.message_handler(func=lambda msg: True)
def process_order(message):
    service = message.text.strip()
    user_id = str(message.from_user.id)
    username = message.from_user.username or message.from_user.first_name

    # Save/update user
    users.update_one(
        {'telegram_id': user_id},
        {'$set': {'username': username, 'last_seen': datetime.datetime.utcnow()}},
        upsert=True
    )

    # Generate payment buttons
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("Pay via UPI", callback_data=f'payment_upi_{service}'),
        InlineKeyboardButton("Pay via Paytm", callback_data=f'payment_paytm_{service}')
    )
    # Add more options as needed

    bot.reply_to(message, "🔹 Select your payment method:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('payment_'))
def handle_payment(call):
    _, method, service = call.data.split('_', 2)
    user_id = str(call.from_user.id)

    # Example price - adjust per your service
    price = 699  # ₹699 for Hotstar Super, for example

    # Save order to MongoDB
    order = {
        'user_id': user_id,
        'service': service,
        'amount': price,
        'payment_method': method,
        'status': 'pending',
        'created_at': datetime.datetime.utcnow()
    }
    orders.insert_one(order)

    # Respond with UPI/Paytm scanner image and instructions
    if method == 'upi':
        photo_url = "https://yourdomain.com/upi-scanner.jpg"  # REPLACE WITH YOUR IMAGE LINK
        instructions = """🟢 **How to Pay via UPI:**
1. Open your UPI app (GPay, PhonePe, Paytm, etc.)
2. Scan the QR code above to pay.
3. After payment, send a screenshot of the receipt here.
4. Your login details will be delivered within 15–30 minutes after verification.
"""
    elif method == 'paytm':
        photo_url = "https://yourdomain.com/paytm-scanner.jpg"  # REPLACE WITH YOUR IMAGE LINK
        instructions = """🔵 **How to Pay via Paytm:**
1. Open Paytm app.
2. Scan the QR code above to pay.
3. After payment, send a screenshot here.
4. We'll deliver your login details soon.
"""

    bot.send_photo(call.message.chat.id, photo_url, caption=instructions)
    bot.send_message(call.message.chat.id, f"📝 **Order Received**\nService: {service}\nAmount: ₹{price}\n\n👉 Please send your payment screenshot for verification.")

# (Optional: Automate delivery confirmation after manual payment verification via a separate script/process.)

@app.route('/', methods=['GET'])
def health_check():
    return "OK", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    json_data = request.get_json()
    update = telebot.types.Update.de_json(json_data)
    bot.process_new_updates([update])
    return 'ok', 200

if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=os.environ.get('WEBHOOK_URL', 'https://your-koyeb-app-name.koyeb.app/webhook'))
    app.run(host='0.0.0.0', port=PORT)
