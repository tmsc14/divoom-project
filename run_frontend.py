from flask import Flask, jsonify, request, send_from_directory
from pixoo import Pixoo
from _helpers import try_to_request, parse_bool_value
import os

# Configuration and Initialization
pixoo_host = os.getenv('PIXOO_HOST', '192.168.1.100')  # Replace with your Pixoo's IP
pixoo_screen = int(os.getenv('PIXOO_SCREEN_SIZE', 64))
pixoo_debug = parse_bool_value(os.getenv('PIXOO_DEBUG', 'false'))

pixoo = Pixoo(pixoo_host, pixoo_screen, pixoo_debug)

# Application Setup
app = Flask(__name__, static_folder='views', static_url_path='')

# Dummy KPI data for demonstration
kpi_data = {
    "green_flags": 10,
    "red_flags": 5,
    "attendance": 85
}

@app.route('/')
def serve_dashboard():
    return send_from_directory(app.static_folder, 'dashboard.html')

@app.route('/api/kpi-data', methods=['GET'])
def get_kpi_data():
    return jsonify(kpi_data)

@app.route('/api/update-kpis', methods=['POST'])
def update_kpis():
    data = request.json

    # Update KPI values
    kpi_data['green_flags'] = data.get('green_flags', kpi_data['green_flags'])
    kpi_data['red_flags'] = data.get('red_flags', kpi_data['red_flags'])
    kpi_data['attendance'] = data.get('attendance', kpi_data['attendance'])

    # Push to Pixoo
    update_pixoo_display(kpi_data)

    return jsonify(status='success', data=kpi_data)

def update_pixoo_display(kpi_data):
    if not try_to_request(f'http://{pixoo_host}/get'):
        print("Pixoo device is not reachable!")
        return

    try:
        # Clear the display (e.g., fill with black background)
        pixoo.fill_rgb(0, 0, 0)  # You might adjust these parameters depending on your background color need

        # Draw KPI Values on Pixoo Display
        pixoo.draw_text_at_location_rgb(f"Green Flags: {kpi_data['green_flags']}", 0, 0, 0, 255, 0)
        pixoo.draw_text_at_location_rgb(f"Red Flags: {kpi_data['red_flags']}", 0, 10, 255, 0, 0)
        pixoo.draw_text_at_location_rgb(f"Attendance: {kpi_data['attendance']}%", 0, 20, 0, 0, 255)

        pixoo.push()  # Ensure these changes are immediately sent to the display
    except Exception as e:
        print(f"Error updating Pixoo display: {e}")

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8000)