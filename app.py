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

MAP_BASE_URL = os.environ.get("MAP_BASE_URL", "")

def make_map_link(frm, to):
    if not MAP_BASE_URL:
        return ""
    return f"{MAP_BASE_URL}/?from={frm}&to={to}"

AIRPORT_CONTEXT = """You are SkyMate, a friendly AI airport navigation assistant for Indira Gandhi International Airport (DEL), Terminal 3, New Delhi.

YOUR PERSONALITY: Warm, helpful, concise. Use emojis. Give step-by-step directions. Always mention walking time. Respond in whatever language the passenger uses.

TERMINAL 3 INFO: 4 levels. Level 1: Arrivals/baggage. Level 2: Immigration. Level 3: Check-in. Level 4: Departures/security/gates/lounges.

GATES: Domestic 1-28 (left wing). International 29-56 (right wing). Gate 1-14: straight then left (5-10 min). Gate 15-28: straight then right (5-12 min). Gate 29-40: after immigration, left (8-15 min). Gate 41-56: after immigration, right (10-18 min).

FOOD: Domestic side (Gate 14-16): Burger King, Starbucks, Haldirams, Punjab Grill. International (Gate 35-38): Costa Coffee, Bikkgane Biryani, Subway. Pre-security (Level 3): McDonalds, Cafe Delhi Heights.

RESTROOMS: Near Gate 5, 12, 20, 28, 35, 42, 50. Family: Gate 12, 35.

LOUNGES: Plaza Premium near Gate 14/36 (Rs 2500). ITC Green near Gate 20 (Rs 2000). Air India Maharaja near Gate 30. Travel Club near Gate 8 (Rs 1800).

BAGGAGE: Level 1. Domestic belts 1-8. International belts 9-16. When asked about status, simulate realistic tracking response like: Your baggage (Tag DEL-38291) has been security screened and is currently being loaded onto your aircraft.

TRANSFERS: T3 Dom to T3 Intl: follow signs, Level 2 transfer desk, re-security, immigration (90 min). T3 to T1: shuttle bus every 15 min (20 min ride). T3 Intl to T3 Dom: transfer desk, security (60 min).

TRANSPORT: Metro Level 1 (Rs 60, 20 min to New Delhi). Pre-paid taxi at exit. Uber/Ola at Parking P3.

RULES: Be accurate. Be concise (under 300 words). Use bullet points for directions. Include walking times. If you do not know something, say so honestly. For emergencies, suggest contacting airport staff."""

def parse_checkin_message(message):
    try:
        parts = message.split("|")
        if len(parts) >= 7 and parts[0].upper() == "CHECKIN":
            return {"name": parts[1], "flight": parts[2], "route": parts[3], "terminal": parts[4], "gate": parts[5], "departure_time": parts[6]}
    except:
        pass
    return None

def is_security_request(text):
    t = (text or "").lower()
    keywords = ["security", "screening", "clearance", "queue", "wait time", "waiting time", "how long is security", "security line"]
    return any(k in t for k in keywords)

def get_ai_response(user_message, passenger_info=None):
    try:
        context = AIRPORT_CONTEXT
        est_wait, wait_status = get_estimated_wait_time()
        if est_wait:
            context += "\nSECURITY: Current wait ~{} min ({}). Share if asked.".format(est_wait, wait_status)
        if passenger_info:
            context += "\nPASSENGER: {} on flight {} ({}), {}, {}, departing {}.".format(
                passenger_info["name"], passenger_info["flight"], passenger_info["route"],
                passenger_info["terminal"], passenger_info["gate"], passenger_info["departure_time"])
            alert = get_security_alert(passenger_info["departure_time"])
            if alert:
                context += "\nALERT: " + alert
        chat = model.start_chat(history=[])
        response = chat.send_message("SYSTEM: {}\n\nPASSENGER MESSAGE: {}".format(context, user_message))
        return response.text
    except Exception as e:
        return "Having trouble right now. Try again!\nError: " + str(e)

@app.route("/")
def home():
    est, status = get_estimated_wait_time()
    return "<h1>SkyMate - Airport Bot</h1><p>Status: Online</p><p>Airport: Delhi T3</p><p>Security: ~{} min ({})</p>".format(est, status)

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
        sec_line = ""
        if est:
            sec_line = "\n\U0001f6a6 Security Wait: ~{} min ({})".format(est, wst)

        alert_line = ""
        alert = get_security_alert(passenger_info["departure_time"])
        if alert:
            alert_line = "\n\n\u26a0\ufe0f " + alert

        welcome = (
            "\u2708\ufe0f *Welcome to Delhi Airport, {}!*\n\n"
            "\U0001f6eb Flight: {}\n"
            "\U0001f4cd Route: {}\n"
            "\U0001f3e2 Terminal: {}\n"
            "\U0001f4cc Gate: {}\n"
            "\U0001f552 Departure: {}"
            "{}"
            "{}\n\n"
            "\U0001f916 I'm *SkyMate*, your airport buddy!\n\n"
            "Try asking:\n"
            "1\ufe0f\u20e3 Take me to my gate\n"
            "2\ufe0f\u20e3 How long is security right now?\n"
            "3\ufe0f\u20e3 Where can I eat near my gate?\n"
            "4\ufe0f\u20e3 Any lounge near my gate?\n"
            "5\ufe0f\u20e3 Is my baggage loaded?\n"
            "6\ufe0f\u20e3 Connecting flight help\n\n"
            "Just type your question \U0001f60a"
        ).format(
            passenger_info["name"], passenger_info["flight"],
            passenger_info["route"], passenger_info["terminal"],
            passenger_info["gate"], passenger_info["departure_time"],
            sec_line, alert_line
        )
        msg.body(welcome)
        return str(resp)

    text = incoming_msg.lower()
    p_info = get_passenger(sender)

    # --- DAY 4: Direct security response (fast, no Gemini needed) ---
    if is_security_request(incoming_msg):
        est_wait, wait_status = get_estimated_wait_time()
        if est_wait is None:
            msg.body("\U0001f6a6 Security wait data is not available right now. Try again in a minute.")
            return str(resp)
        sec_msg = "\U0001f6a6 Current security clearance: ~{} min ({})".format(est_wait, wait_status)
        if p_info:
            alert = get_security_alert(p_info["departure_time"])
            if alert:
                sec_msg += "\n\n\u26a0\ufe0f " + alert
        msg.body(sec_msg)
        return str(resp)

    # --- Gate / Navigation (your Day 3 logic preserved) ---
    if "gate" in text or "my gate" in text or "take me" in text or "navigate" in text or "direction" in text:
        if p_info and p_info.get("gate", "").lower().replace(" ", "") in ["gate36", "36"]:
            link = make_map_link("SECURITY", "GATE36")
            if link:
                ai_text = get_ai_response(incoming_msg, p_info)
                msg.body(f"{ai_text}\n\n\U0001f5fa *Route on map:*\n\U0001f449 {link}")
                return str(resp)

    # --- Restroom ---
    if "restroom" in text or "toilet" in text or "washroom" in text or "bathroom" in text:
        link = make_map_link("GATE36", "RESTROOM")
        if link:
            ai_text = get_ai_response(incoming_msg, p_info)
            msg.body(f"{ai_text}\n\n\U0001f6bb *Restroom route:*\n\U0001f449 {link}")
            return str(resp)

    # --- Lounge ---
    if "lounge" in text:
        link = make_map_link("SECURITY", "LOUNGE")
        if link:
            ai_text = get_ai_response(incoming_msg, p_info)
            msg.body(f"{ai_text}\n\n\U0001f6cb *Lounge route:*\n\U0001f449 {link}")
            return str(resp)

    # --- Food ---
    if "food" in text or "eat" in text or "restaurant" in text or "hungry" in text:
        link = make_map_link("SECURITY", "FOOD")
        if link:
            ai_text = get_ai_response(incoming_msg, p_info)
            msg.body(f"{ai_text}\n\n\U0001f354 *Food court route:*\n\U0001f449 {link}")
            return str(resp)

    # --- Default: Gemini AI ---
    msg.body(get_ai_response(incoming_msg, p_info))
    return str(resp)

if __name__ == "__main__":
    app.run(debug=True, port=5000)