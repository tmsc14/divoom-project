import csv
from flask import Flask, jsonify, request, send_from_directory
from pixoo import Pixoo
from datetime import datetime
from pytz import timezone
from _helpers import try_to_request, parse_bool_value
import os
from PIL import Image

# Configuration and Initialization
pixoo_host = os.getenv('PIXOO_HOST', '192.168.1.100')  # Your Pixoo's IP
pixoo_screen = int(os.getenv('PIXOO_SCREEN_SIZE', 64))
pixoo_debug = parse_bool_value(os.getenv('PIXOO_DEBUG', 'false'))

pixoo = Pixoo(pixoo_host, pixoo_screen, pixoo_debug)

# Flask app setup
app = Flask(__name__, static_folder='views', static_url_path='')

# CSV file path
CSV_FILE_PATH = 'dataset/data.csv'

country_timezones = {
    "Australia": "Australia/Sydney",
    "Philippines": "Asia/Manila",
    "United States": "America/New_York",
    "India": "Asia/Kolkata",
    "Colombia": "America/Bogota"
}

def read_kpi_data_from_csv():
    try:
        with open(CSV_FILE_PATH, mode='r') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                return {
                    "green_flags": int(row.get("green_flags", 0)),
                    "red_flags": int(row.get("red_flags", 0)),
                    "attendance": int(row.get("attendance", 0)),
                    "showDateTime": parse_bool_value(row.get("showDateTime", "false")),
                    "country": row.get("country", "Australia")
                }
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return {"green_flags": 0, "red_flags": 0, "attendance": 0, "showDateTime": False, "country": "Australia"}

def write_kpi_data_to_csv(kpi_data):
    try:
        with open(CSV_FILE_PATH, mode='w', newline='') as file:
            csv_writer = csv.DictWriter(file, fieldnames=["green_flags", "red_flags", "attendance", "showDateTime", "country"])
            csv_writer.writeheader()
            csv_writer.writerow({
                "green_flags": kpi_data["green_flags"],
                "red_flags": kpi_data["red_flags"],
                "attendance": kpi_data["attendance"],
                "showDateTime": kpi_data["showDateTime"],
                "country": kpi_data["country"]
            })
    except Exception as e:
        print(f"Error writing to CSV file: {e}")

@app.route('/')
def serve_dashboard():
    return send_from_directory(app.static_folder, 'dashboard.html')

@app.route('/api/kpi-data', methods=['GET'])
def get_kpi_data():
    kpi_data = read_kpi_data_from_csv()
    return jsonify(kpi_data)

@app.route('/api/update-kpis', methods=['POST'])
def update_kpis():
    kpi_data = request.json
    write_kpi_data_to_csv(kpi_data)

    # Push to Pixoo
    update_pixoo_display(kpi_data)

    return jsonify(status='success', data=kpi_data)

def update_pixoo_display(kpi_data):
    if not try_to_request(f'http://{pixoo_host}/get'):
        print("Pixoo device is not reachable!")
        return

    try:
        pixoo.fill_rgb(0, 0, 0)  # Clear the display

        # Load and draw the green flag
        green_image_path = 'views/img/greenflag.png'
        with Image.open(green_image_path) as green_img:
            green_img = green_img.resize((10, 10))
            pixoo.draw_image_at_location(green_img, 3, 5)

        # Draw text for the green flag value
        pixoo.draw_text_at_location_rgb(f"{kpi_data['green_flags']}", 18, 7, 0, 255, 0)

        # Load and draw the red flag
        red_image_path = 'views/img/redflag.png'
        with Image.open(red_image_path) as red_img:
            red_img = red_img.resize((10, 10))
            pixoo.draw_image_at_location(red_img, 3, 20)

        # Draw text for the red flag value
        pixoo.draw_text_at_location_rgb(f"{kpi_data['red_flags']}", 18, 22, 255, 0, 0)

        # Load and draw the check icon
        check_image_path = 'views/img/check.png'
        with Image.open(check_image_path) as check_img:
            check_img = check_img.resize((10, 10))
            pixoo.draw_image_at_location(check_img, 3, 35)

        # Draw text for attendance
        pixoo.draw_text_at_location_rgb(f"{kpi_data['attendance']}%", 18, 37, 0, 0, 255)

        # Draw date, time (24-hour format), and country code if the toggle is enabled
        if kpi_data.get("showDateTime"):
            tz = timezone(country_timezones.get(kpi_data["country"], "Australia/Sydney"))
            now = datetime.now(tz)
            now_date = now.strftime("%d-%b-%y")   # Example: "12-Mar-25"
            now_time = now.strftime("%H:%M")      # Example: "22:47" (24-hour format)
            country_code = {
                "Australia": "AU",
                "Philippines": "PH",
                "United States": "US",
                "India": "IN",
                "Colombia": "CO"
            }.get(kpi_data["country"], "AU")

            # Display country code on one line, and date/time on the next line
            pixoo.draw_text_at_location_rgb(country_code, 2, 52, 255, 180, 0)
            pixoo.draw_text_at_location_rgb(f"{now_date} {now_time}", 2, 58, 255, 180, 0)

        pixoo.push()

    except Exception as e:
        print(f"Error updating Pixoo display: {e}")
        
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8000)