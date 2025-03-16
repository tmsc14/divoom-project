import csv
from flask import Flask, jsonify, request, send_from_directory
from pixoo import Pixoo
from datetime import datetime
from pytz import timezone
from _helpers import try_to_request, parse_bool_value
import os
from PIL import Image
import threading
import time

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
    update_pixoo_display(kpi_data)
    return jsonify(status='success', data=kpi_data)

def load_frames_from_directory(folder_path, prefix, num_frames):
    """Load frames with a specific prefix from a directory."""
    frames = []
    for i in range(1, num_frames + 1):
        frame_path = f"{folder_path}/{prefix}-frame{i}.png"
        if os.path.exists(frame_path):
            with Image.open(frame_path) as img:
                frames.append(img.resize((10, 10)))
        else:
            print(f"Frame not found: {frame_path}")
    return frames

def animate_loop(frames_collection):
    """Animate the frames, assuming each set of frames is located uniquely on the same display."""
    while True:
        for gf, rf, af in zip(*frames_collection):
            # Draw frames
            pixoo.draw_image_at_location(gf, 3, 5)
            pixoo.draw_image_at_location(rf, 3, 20)
            pixoo.draw_image_at_location(af, 3, 35)

            pixoo.push()
            time.sleep(1)

def update_static_elements(kpi_data):
    pixoo.fill_rgb(0, 0, 0)  # Clear the display

    # Draw grid lines
    for y in range(0, 47):
        pixoo.draw_pixel_at_location_rgb(32, y, 255, 255, 255)
    for x in range(0, 32):
        pixoo.draw_pixel_at_location_rgb(x, 17, 255, 255, 255)
        pixoo.draw_pixel_at_location_rgb(x, 32, 255, 255, 255)
    for x in range(0, 64):
        pixoo.draw_pixel_at_location_rgb(x, 47, 255, 255, 255)

    # Draw static text
    pixoo.draw_text_at_location_rgb(f"{kpi_data['green_flags']}", 18, 7, 0, 255, 0)
    pixoo.draw_text_at_location_rgb(f"{kpi_data['red_flags']}", 18, 22, 255, 0, 0)
    pixoo.draw_text_at_location_rgb(f"{kpi_data['attendance']}%", 18, 37, 0, 0, 255)

    if kpi_data.get("showDateTime"):
        tz = timezone(country_timezones.get(kpi_data["country"], "Australia/Sydney"))
        now = datetime.now(tz)
        now_date = now.strftime("%d-%b-%y")
        now_time = now.strftime("%H:%M")
        country_code = {
            "Australia": "AU",
            "Philippines": "PH",
            "United States": "US",
            "India": "IN",
            "Colombia": "CO"
        }.get(kpi_data["country"], "AU")

        pixoo.draw_text_at_location_rgb(country_code, 2, 51, 255, 180, 0)
        pixoo.draw_text_at_location_rgb(f"{now_date} {now_time}", 2, 57, 255, 180, 0)

    pixoo.push()

def update_pixoo_display(kpi_data):
    if not try_to_request(f"http://{pixoo_host}/get"):
        print("Pixoo device is not reachable!")
        return

    try:
        # Display static elements first
        update_static_elements(kpi_data)

        # Load frames for animations
        green_frames = load_frames_from_directory('views/img/green-flag-frames', 'GF', 5)
        red_frames = load_frames_from_directory('views/img/red-flag-frames', 'RF', 5)
        attendance_frames = load_frames_from_directory('views/img/attendance-frames', 'AF', 2)

        # Start animation in a single thread
        threading.Thread(target=animate_loop, args=(([green_frames, red_frames, attendance_frames]),), daemon=True).start()

    except Exception as e:
        print(f"Error updating Pixoo display: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8000)