import csv
from flask import Flask, jsonify, request, send_from_directory
from pixoo import Pixoo
from datetime import datetime
from pytz import timezone
from _helpers import try_to_request, parse_bool_value
import os
import threading
import time
from PIL import Image, ImageDraw, ImageFont
from pytz import timezone, country_timezones

# Configuration and Initialization
pixoo_host = os.getenv("PIXOO_HOST", "192.168.1.100")  # Your Pixoo's IP address
pixoo_screen = int(os.getenv("PIXOO_SCREEN_SIZE", 64))
pixoo_debug = parse_bool_value(os.getenv("PIXOO_DEBUG", "false"))

pixoo = Pixoo(pixoo_host, pixoo_screen, pixoo_debug)

# Flask app setup
app = Flask(__name__, static_folder="views", static_url_path="")

# CSV file path
CSV_FILE_PATH = "dataset/data.csv"

country_timezones = {
    "Australia": "Australia/Sydney",
    "Philippines": "Asia/Manila",
    "United States": "America/New_York",
    "India": "Asia/Kolkata",
    "Colombia": "America/Bogota",
}

# Global variables for animation control
animation_thread = None
stop_animation = False
animation_lock = threading.Lock()  # To prevent race conditions

def read_kpi_data_from_csv():
    try:
        with open(CSV_FILE_PATH, mode="r") as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                return {
                    "green_flags": int(row.get("green_flags", 0)),
                    "red_flags": int(row.get("red_flags", 0)),
                    "attendance": int(row.get("attendance", 0)),
                    "showDateTime": parse_bool_value(row.get("showDateTime", "false")),
                    "country": row.get("country", "Australia"),
                    "background_color": row.get("background_color", "0,0,0"),
                    "text_color": row.get("text_color", "255,255,255"),
                    "line_color": row.get("line_color", "255,255,255"),
                }
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return {
            "green_flags": 0,
            "red_flags": 0,
            "attendance": 0,
            "showDateTime": False,
            "country": "Australia",
            "background_color": "0,0,0",
            "text_color": "255,255,255",
            "line_color": "255,255,255",
        }

def write_kpi_data_to_csv(kpi_data):
    try:
        with open(CSV_FILE_PATH, mode="w", newline="") as file:
            csv_writer = csv.DictWriter(
                file,
                fieldnames=[
                    "green_flags",
                    "red_flags",
                    "attendance",
                    "showDateTime",
                    "country",
                    "background_color",
                    "text_color",
                    "line_color",
                ],
            )
            csv_writer.writeheader()
            csv_writer.writerow(kpi_data)
    except Exception as e:
        print(f"Error writing to CSV file: {e}")

@app.route("/")
def serve_dashboard():
    return send_from_directory(app.static_folder, "dashboard.html")

@app.route("/api/kpi-data", methods=["GET"])
def get_kpi_data():
    kpi_data = read_kpi_data_from_csv()
    return jsonify(kpi_data)

@app.route("/api/update-kpis", methods=["POST"])
def update_kpis():
    global animation_thread, stop_animation

    # Stop the existing animation thread
    with animation_lock:
        if animation_thread is not None:
            stop_animation = True
            animation_thread.join()
            stop_animation = False

    # Update KPI data
    kpi_data = request.json
    write_kpi_data_to_csv(kpi_data)

    # Update Pixoo display
    update_pixoo_display(kpi_data)

    return jsonify(status="success", data=kpi_data)

def load_frames_from_directory(folder_path, prefix, num_frames):
    """Load frames with a specific prefix from a directory."""
    frames = []
    for i in range(1, num_frames + 1):
        frame_path = f"{folder_path}/{prefix}-frame{i}.png"
        if os.path.exists(frame_path):
            with Image.open(frame_path) as img:
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                frames.append(img.resize((10, 10), Image.LANCZOS))
        else:
            print(f"Frame not found: {frame_path}")
    return frames

def format_kpi_value(value):
    value = int(value)  # Ensure it's an integer
    if value >= 1000:
        return f"{value / 1000:.1f}k" if value < 10000 else f"{value // 1000}k"
    return str(value)

def animate_loop(frames_collection, static_background):
    """Animate the frames while maintaining the static background."""
    while not stop_animation:
        for gf, rf, af in zip(*frames_collection):
            if stop_animation:
                break

            # Create a copy of the static background
            combined = static_background.copy()

            # Paste the frames with transparency
            combined.paste(gf, (2, 2), gf)  # Use the image itself as the mask
            combined.paste(rf, (2, 17), rf)  # Use the image itself as the mask
            combined.paste(af, (2, 32), af)  # Use the image itself as the mask

            # Convert the combined image to RGB (Pixoo doesn't support RGBA)
            combined_rgb = combined.convert("RGB")

            # Send the combined image to the Pixoo device
            try:
                pixoo.draw_image(combined_rgb)
                pixoo.push()
            except Exception as e:
                print(f"Error updating Pixoo display: {e}")
                break

            time.sleep(1)

def update_static_elements(kpi_data):
    # Parse colors
    bg_r, bg_g, bg_b = map(int, kpi_data["background_color"].split(","))
    text_r, text_g, text_b = map(int, kpi_data["text_color"].split(","))
    line_r, line_g, line_b = map(int, kpi_data["line_color"].split(","))

    # Create a new image
    static_img = Image.new("RGBA", (pixoo_screen, pixoo_screen), (bg_r, bg_g, bg_b))
    draw = ImageDraw.Draw(static_img)

    # Load font (fallback to default if needed)
    try:
        font = ImageFont.truetype("views/fonts/PressStart2P.ttf", 7.5)  # 6px font to fit the bottom section
    except IOError:
        try:
            font = ImageFont.truetype("views/fonts/TinyUnicode.ttf", 6)
        except IOError:
            font = ImageFont.load_default()

    # Adjusted grid lines (moved up by 3 pixels)
    for y in range(0, 44):  # Reduced height by 3 pixels
        draw.point((46, y), fill=(line_r, line_g, line_b))
    for x in range(0, 46):
        draw.point((x, 14), fill=(line_r, line_g, line_b))  # Moved up from 17
        draw.point((x, 29), fill=(line_r, line_g, line_b))  # Moved up from 32
    for x in range(0, 64):
        draw.point((x, 44), fill=(line_r, line_g, line_b))  # Moved up from 47

    # Adjusted KPI text (moved up by 3 pixels)
    draw.text((14, 4), format_kpi_value(kpi_data['green_flags']), fill=(text_r, text_g, text_b), font=font)
    draw.text((14, 19), format_kpi_value(kpi_data['red_flags']), fill=(text_r, text_g, text_b), font=font)
    draw.text((14, 34), format_kpi_value(kpi_data['attendance']), fill=(text_r, text_g, text_b), font=font)

    # Display Date/Time if enabled (also shifted up)
    if kpi_data.get("showDateTime"):
        tz = timezone(country_timezones.get(kpi_data["country"], "Australia/Sydney"))
        now = datetime.now(tz)
        now_date = now.strftime("%d/%m/%y")  # Example: 18-Mar-25
        now_time = now.strftime("%H:%M")  # Example: 14:45

        # Get country code mapping
        country_code = {
            "Australia": "AU",
            "Philippines": "PH",
            "United States": "US",
            "India": "IN",
            "Colombia": "CO",
        }.get(kpi_data["country"], "AU")

        # Adjusted positions (moved up by 3 pixels)
        draw.text((2, 46), country_code, fill=(text_r, text_g, text_b), font=font)  # Moved up from (2, 49)
        draw.text((23, 46), now_time, fill=(text_r, text_g, text_b), font=font)  # Moved up from (50, 49)
        draw.text((0, 55), now_date, fill=(text_r, text_g, text_b), font=font) # Moved up from (2, 57)

    return static_img

def update_pixoo_display(kpi_data):
    global animation_thread

    if not try_to_request(f"http://{pixoo_host}/get"):
        print("Pixoo device is not reachable!")
        return

    try:
        # Display static elements first and get the static background
        static_background = update_static_elements(kpi_data)

        # Load frames for animations
        green_frames = load_frames_from_directory("views/img/green-flag-frames", "GF", 5)
        red_frames = load_frames_from_directory("views/img/red-flag-frames", "RF", 5)
        attendance_frames = load_frames_from_directory("views/img/attendance-frames", "AF", 2)

        # Start animation in a thread
        with animation_lock:
            if animation_thread is not None:
                stop_animation = True
                animation_thread.join()
                stop_animation = False

            animation_thread = threading.Thread(
                target=animate_loop,
                args=([green_frames, red_frames, attendance_frames], static_background),
                daemon=True,
            )
            animation_thread.start()

    except Exception as e:
        print(f"Error updating Pixoo display: {e}")

# Start Flask app
if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8000)