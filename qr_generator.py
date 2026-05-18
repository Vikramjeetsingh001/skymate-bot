import qrcode
import urllib.parse
import os

TWILIO_NUMBER = "14155238886"  # Twilio sandbox WhatsApp number (no +)

passengers = [
    {"name": "Vikramjeet Singh", "flight": "AI302", "route": "DEL-DXB", "terminal": "T3",
     "gate": "Gate36", "time": "14:30"},
    {"name": "Rahul Sharma", "flight": "UK112", "route": "DEL-BOM", "terminal": "T3",
     "gate": "Gate12", "time": "16:45"},
    {"name": "Sarah Khan", "flight": "EK203", "route": "DEL-DXB", "terminal": "T3",
     "gate": "Gate42", "time": "19:00"},
    {"name": "Amit Patel", "flight": "SG456", "route": "DEL-BLR", "terminal": "T3",
     "gate": "Gate8", "time": "11:15"},
]
os.makedirs("qr_codes", exist_ok=True)

for p in passengers:
    message = "CHECKIN|{}|{}|{}|{}|{}|{}".format(
        p["name"],
        p["flight"],
        p["route"],
        p["terminal"],
        p["gate"],
        p["time"]
    )

    encoded = urllib.parse.quote(message)
    url = "https://wa.me/{}?text={}".format(TWILIO_NUMBER, encoded)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    safe_name = p["name"].replace(" ", "_").lower()
    filename = "qr_codes/{}_boarding_qr.png".format(safe_name)
    img.save(filename)

    print("QR generated:", filename)

print("✅ All QR codes saved in qr_codes folder!")