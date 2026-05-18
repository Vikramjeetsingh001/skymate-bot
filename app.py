import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai
from database import save_passenger, get_passenger, init_db
from security_engine import get_estimated_wait_time, get_security_alert, populate_simulated_data

app = Flask(__name__)
init_db()
populate_simulated_data()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

AIRPORT_CONTEXT = """You are SkyMate, a friendly AI airport navigation assistant for Indira Gandhi International Airport (DEL), Terminal 3, New Delhi.

YOUR PERSONALITY: Warm, helpful, concise. Use emojis. Give step-by-step directions. Always mention walking time. Respond in whatever language the passenger uses.

TERMINAL 3 INFO: 4 levels. Level 1: Arrivals/baggage. Level 2: Immigration. Level 3: Check-in. Level 4: Departures/security/gates/lounges.

GATES: Domestic 1-28 (left wing). International 29-56 (right wing). Gate 1-14: straight then left (5-10 min). Gate 15-28: straight then right (5-12 min). Gate 29-40: after immigration, left (8-15 min). Gate 41-56: after immigration, right (10-18 min).

FOOD: Domestic side (Gate 14-16): Burger King, Starbucks, Haldirams, Punjab Grill. International (Gate 35-38): Costa Coffee, Bikkgane Biryani, Subway. Pre-security (Level 3): McDonalds, Cafe Delhi Heights.

RESTROOMS: Near Gate 5, 12, 20, 28, 35, 42, 50. Family: Gate 12, 35.

LOUNGES: Plaza Premium near Gate 14/36 (Rs 2500). ITC Green near Gate 20 (Rs 2000). Air India Maharaja near Gate 30. Travel Club near Gate 8 (Rs 1800).

BAGGAGE: Level 1. Domestic belts 1-8. International belts 9-16. When asked about status, simulate realistic tracking response.

TRANSFERS: T3 Dom to T3 Intl: follow signs, Level 2 transfer desk, re-security, immigration (90 min). T3 to T1: shuttle bus every 15 min (20 min ride). T3 Intl to T3 Dom: transfer desk, security (60 min).

TRANSPORT: Metro Level 1 (Rs 60, 20 min to New Delhi). Pre-paid taxi at exit. Uber/Ola at Parking P3.

RULES: Be accurate. Be concise (under 300 words). Use bullet points for directions. Include walking times."""

def parse_checkin_message(message):
    try:
        parts = message.split("|")
        if len(parts) >= 7 and parts[0].upper() == "CHECKIN":
            return {
                "name": parts[1],
                "flight": parts[2],
                "route": parts[3],
                "terminal": parts[4],
                "gate": parts[5],
                "departure_time": parts[6]
            }
    except:
        pass
    return None

def get_ai_response(user_message, passenger_info=None):
    try:
        context = AIRPORT_CONTEXT
        est_wait, wait_status = get_estimated_wait_time()
        if est_wait:
            context += "\nSECURITY: Current wait ~{} min ({}). Share if asked.".format(
                est_wait,
                wait_status
            )
        if passenger_info:
            context += "\nPASSENGER: {} on flight {} ({}), {}, {}, departing {}.".format(
                passenger_info["name"],
                passenger_info["flight"],
                passenger_info["route"],
                passenger_info["terminal"],
                passenger_info["gate"],
                passenger_info["departure_time"]
            )
            alert = get_security_alert(passenger_info["departure_time"])
            if alert:
                context += "\nALERT: " + alert
        chat = model.start_chat(history=[])
        response = chat.send_message(
            "SYSTEM: {}\n\nPASSENGER MESSAGE: {}".format(
                context,
                user_message
            )
        )
        return response.text
    except Exception as e:
        return "Having trouble right now. Try again!\nError: " + str(e)

@app.route("/")
def home():
    est, status = get_estimated_wait_time()

    return "<h1>SkyMate - Airport Bot</h1><p>Status: Online</p><p>Airport: Delhi T3</p><p>Security: ~{} min ({})</p>".format(
        est,
        status
    )

@app.route("/webhook", methods=["POST"])
def webhook():
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")
    resp = MessagingResponse()
    msg = resp.message()
    passenger_info = parse_checkin_message(incoming_msg)
    if passenger_info:
        save_passenger(sender, passenger_info)
        est, wst = get_estimated_wait_time()
        sec = "\nSecurity Wait: ~{} min ({})".format(est, wst) if est else ""
        welcome = (
            "Welcome to Delhi Airport, {}!\n\n"
            "Flight: {}\n"
            "Route: {}\n"
            "Terminal: {}\n"
            "Gate: {}\n"
            "Departure: {}\n{}\n\n"
            "I am *SkyMate*, your airport buddy!\n\n"
            "I can help with:\n"
            "- *Navigate* to gate\n"
            "- *Food* nearby\n"
            "- *Restroom* nearest\n"
            "- *Lounge* access/prices\n"
            "- *Baggage* tracking\n"
            "- *Transfer* connecting flights\n"
            "- *Security* wait time\n"
            "- *Any language* just type!\n\n"
            "Ask me anything!"
        ).format(
            passenger_info["name"],
            passenger_info["flight"],
            passenger_info["route"],
            passenger_info["terminal"],
            passenger_info["gate"],
            passenger_info["departure_time"],
            sec
        )

        msg.body(welcome)
    else:
        p_info = get_passenger(sender)
        msg.body(get_ai_response(incoming_msg, p_info))
    return str(resp)

if __name__ == "__main__":
    app.run(debug=True, port=5000)