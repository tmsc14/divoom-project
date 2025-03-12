from flask import Flask, jsonify, request, send_from_directory
from pixoo import Pixoo
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

def read_kpi_data_from_csv():
    try:
        with open(CSV_FILE_PATH, mode='r') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                return {key: int(value) for key, value in row.items()}
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return {"green_flags": 0, "red_flags": 0, "attendance": 0}

def write_kpi_data_to_csv(kpi_data):
    try:
        with open(CSV_FILE_PATH, mode='w', newline='') as file:
            csv_writer = csv.DictWriter(file, fieldnames=kpi_data.keys())
            csv_writer.writeheader()
            csv_writer.writerow(kpi_data)
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
            green_img = green_img.resize((10, 10))  # Resize to desired dimensions
            pixoo.draw_image_at_location(green_img, 3, 5)  # Position slightly lower to center the related text

        # Draw text for the green flag value
        pixoo.draw_text_at_location_rgb(f"{kpi_data['green_flags']}", 18, 7, 0, 255, 0)  # Adjust the vertical position of the text

        # Load and draw the red flag lower on the display
        red_image_path = 'views/img/redflag.png'
        with Image.open(red_image_path) as red_img:
            red_img = red_img.resize((10, 10))
            pixoo.draw_image_at_location(red_img, 3, 20)  # Position the red flag lower than the green flag

        # Draw text for the red flag value
        pixoo.draw_text_at_location_rgb(f"{kpi_data['red_flags']}", 18, 22, 255, 0, 0)

        # Load and draw the check icon
        check_image_path = 'views/img/check.png'
        with Image.open(check_image_path) as check_img:
            check_img = check_img.resize((10, 10))  # Resize to fit comfortably
            pixoo.draw_image_at_location(check_img, 3, 35)

        # Draw text for attendance
        pixoo.draw_text_at_location_rgb(f"{kpi_data['attendance']}%", 18, 37, 0, 0, 255)

        pixoo.push()  # Push the updates to the display

    except Exception as e:
        print(f"Error updating Pixoo display: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8000)