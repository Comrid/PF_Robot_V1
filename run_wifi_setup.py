"""Entry point: run WiFi setup Flask app."""
from wifi_setup.app import app

if __name__ == "__main__":
    from wifi_setup.app import get_default_robot_name
    from wifi_setup import oled
    oled.show_qr_on_oled(get_default_robot_name)
    app.run(host="0.0.0.0", port=5000, debug=False)
