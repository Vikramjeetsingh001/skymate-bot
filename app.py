import os
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import google.generativeai as genai

# ==================================================
# SETUP
# ==================================================
app = Flask(__name__)

# Configure Gemini AI
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# ==================================================
# AIRPORT KNOWLEDGE BASE (Delhi T3)
# ==================================================
AIRPORT_CONTEXT = """
You are SkyMate, a friendly AI airport navigation assistant for
Indira Gandhi International Airport (DEL), Terminal 3, New Delhi.

YOUR PERSONALITY:
- Warm, helpful, concise
- Use emojis to make messages friendly
- Give directions as simple step-by-step instructions
- Always mention estimated walking time
- If asked in Hindi or any other language, respond in that language

TERMINAL 3 INFORMATION:
- Terminal 3 handles both domestic and international flights
- It has 4 levels:
Level 1: Arrivals (baggage claim, exit)
Level 2: Arrivals (immigration for international)
Level 3: Check-in counters
Level 4: Departures (security, gates, lounges)

GATE LAYOUT (Departure Level 4):
- Domestic Gates: 1-28 (left wing after security)
- International Gates: 29-56 (right wing after security)
- Gate 1-14: Walk straight, then left (5-10 min walk)
- Gate 15-28: Walk straight, then right (5-12 min walk)
- Gate 29-40: After immigration, left corridor (8-15 min walk)
- Gate 41-56: After immigration, right corridor (10-18 min walk)

FOOD COURTS:
- After security (domestic): Burger King, Starbucks, Haldirams,
  Punjab Grill, The Beer Cafe - near Gate 14-16
- After immigration (international): Costa Coffee, Bikkgane Biryani,
  Subway, Duty Free food court - near Gate 35-38
- Pre-security: McDonalds, Cafe Delhi Heights - Level 3 near
  check-in counters J-K

RESTROOMS:
- Available near every 5th gate
- Major restrooms: Near Gate 5, Gate 12, Gate 20, Gate 28,
  Gate 35, Gate 42, Gate 50
- Family restrooms: Near Gate 12, Gate 35
- Accessible restrooms: Near Gate 5, Gate 20, Gate 42

LOUNGES:
- Plaza Premium Lounge: Near Gate 14 (domestic), Gate 36 (international)
  Access: Priority Pass, Rs.2500 walk-in
- ITC Green Lounge: Near Gate 20, Access: Business class, Rs.2000 walk-in
- Air India Maharaja Lounge: Near Gate 30, Access: Air India Business/First
- Travel Club Lounge: Near Gate 8, Access: Rs.1800 walk-in

BAGGAGE INFO:
- Baggage claim is at Level 1
- Domestic: Belts 1-8
- International: Belts 9-16
- Oversized baggage: Separate counter near Belt 1 and Belt 9
- Lost baggage counter: Near exit gate, Level 1
- SIMULATED TRACKING: When asked about baggage status, simulate a
  realistic response like:
  "Your baggage (Tag #DEL-38291) has been security screened and is
  currently being loaded onto aircraft AI302. Expected completion: 15 min
  before departure."

CONNECTING FLIGHTS (TERMINAL TRANSFER):
- T3 Domestic to T3 International: Follow Connecting Flights signs
  after landing, Transfer desk at Level 2, Security re-check,
  Immigration, International departure gates (allow 90 min minimum)
- T3 to T1 (Domestic): Free shuttle bus from Transfer Counter,
  runs every 15 min, takes 20 min
- T3 International to T3 Domestic: After immigration/arrival,
  Transfer desk, Security, Domestic gates (allow 60 min minimum)

TRANSPORT FROM AIRPORT:
- Delhi Metro (Airport Express Line): Level 1, follow orange signs,
  runs 5 AM - 11 PM, Rs.60 to New Delhi station (20 min)
- Pre-paid Taxi: Level 1, exit gate, counter on right
- Uber/Ola: Level 1, pickup point is Parking P3

USEFUL CONTACTS:
- Airport Helpdesk: 0124-337-6000
- Lost and Found: 011-2456-5126

RULES:
1. Always be helpful and accurate
2. If you do not know something, say so honestly
3. For emergencies, always suggest contacting airport staff
4. Keep responses concise (under 300 words) for WhatsApp readability
5. Use bullet points or numbered steps for directions
6. When giving gate directions, always include walking time estimate
"""

# ==================================================
# STORE PASSENGER SESSIONS (in-memory)
# ==================================================
passenger_sessions = {}

def parse_checkin_message(message):
    """Parse the QR code message:
    CHECKIN|Name|Flight|Route|Terminal|Gate|Time"""
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
    except Exception:
        pass
    return None

def get_ai_response(user_message, passenger_info=None):
    """Get response from Gemini AI"""
    try:
        context = AIRPORT_CONTEXT

        if passenger_info:
            context += f"""

CURRENT PASSENGER DETAILS:
- Name: {passenger_info['name']}
- Flight: {passenger_info['flight']}
- Route: {passenger_info['route']}
- Terminal: {passenger_info['terminal']}
- Gate: {passenger_info['gate']}
- Departure Time: {passenger_info['departure_time']}

Use these details to give personalized help.
When they say 'my gate' or 'my flight', use the above info.
"""

        chat = model.start_chat(history=[])
        response = chat.send_message(
            f"SYSTEM CONTEXT: {context}\n\nPASSENGER MESSAGE: {user_message}"
        )
        return response.text
    except Exception as e:
        return (
            "I am having trouble connecting right now. "
            "Please try again in a moment!\n\n"
            f"Error: {str(e)}"
        )


# ==================================================
# ROUTES (URL endpoints)
# ==================================================

@app.route("/")
def home():
    return """
    <h1>SkyMate - Airport Navigation Bot</h1>
    <p>The WhatsApp bot is running!</p>
    <p><strong>Status:</strong> Online</p>
    <p>Airport: Delhi T3 (DEL)</p>
    """

@app.route("/webhook", methods=["POST"])
def webhook():
    """Called every time someone sends a WhatsApp message"""

    # Get the message and sender number
    incoming_msg = request.values.get("Body", "").strip()
    sender = request.values.get("From", "")

    # Create Twilio response object
    resp = MessagingResponse()
    msg = resp.message()

    # Check if this is a check-in message (from QR code scan)
    passenger_info = parse_checkin_message(incoming_msg)

    if passenger_info:
        # New passenger scanned QR code!
        passenger_sessions[sender] = passenger_info
        welcome = (
            f"Welcome to Delhi Airport, {passenger_info['name']}!\n\n"
            f"Flight: {passenger_info['flight']}\n"
            f"Route: {passenger_info['route']}\n"
            f"Terminal: {passenger_info['terminal']}\n"
            f"Gate: {passenger_info['gate']}\n"
            f"Departure: {passenger_info['departure_time']}\n\n"
            f"I am *SkyMate*, your airport assistant!\n\n"
            f"I can help you with:\n"
            f"- *Navigate* to your gate\n"
            f"- *Food* nearby restaurants\n"
            f"- *Restroom* nearest ones\n"
            f"- *Lounge* access info\n"
            f"- *Baggage* tracking status\n"
            f"- *Transfer* connecting flights\n"
            f"- *Any language* just type!\n\n"
            f"Ask me anything!"
        )
        msg.body(welcome)
    else:
        # Regular message - use AI
        p_info = passenger_sessions.get(sender, None)
        ai_reply = get_ai_response(incoming_msg, p_info)
        msg.body(ai_reply)

    return str(resp)


# ==================================================
# RUN THE APP
# ==================================================
if __name__ == "__main__":
    app.run(debug=True, port=5000)