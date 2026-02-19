# WiFi setup for V1: Flask app, routes, get_robot_id, get_default_robot_name, restore_ap_mode. OLED always used.
from pathlib import Path
import subprocess
import platform
import time
import threading

from flask import Flask, render_template, request, jsonify, redirect, url_for

from wifi_setup import oled


def get_default_robot_name():
    result = subprocess.run(["cat", "/etc/pf_default_robot_name"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def get_robot_id():
    result = subprocess.run(["cat", "/etc/pf_id"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def restore_ap_mode():
    subprocess.run(["sudo", "nmcli", "con", "up", "Pathfinder-AP"], capture_output=True, timeout=10)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _write_robot_config(robot_id: str, robot_name: str) -> None:
    config_path = _repo_root() / "config" / "robot_config.py"
    text = config_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out = []
    for line in lines:
        s = line.strip()
        if s.startswith("ROBOT_ID ="):
            out.append(f"ROBOT_ID = {repr(robot_id)}")
        elif s.startswith("ROBOT_NAME ="):
            out.append(f"ROBOT_NAME = {repr(robot_name)}")
        else:
            out.append(line)
    config_path.write_text("\n".join(out) + "\n", encoding="utf-8")


app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/robot-name")
def get_robot_name():
    return jsonify({"success": True, "robot_name": get_default_robot_name()})


@app.route("/generate_204")
@app.route("/gen_204")
@app.route("/hotspot-detect.html")
@app.route("/library/test/success.html")
@app.route("/success.txt")
@app.route("/connecttest.txt")
@app.route("/redirect")
@app.route("/ncsi.txt")
def captive_probe_redirect():
    return redirect(url_for("index"), code=302)


@app.route("/connect", methods=["POST"])
def connect():
    try:
        data = request.get_json()
        ssid = data.get("ssid")
        password = data.get("password")

        if not ssid:
            return jsonify({"success": False, "error": "SSID를 입력해주세요."}), 400
        if password and not (8 <= len(password) <= 63):
            return jsonify({"success": False, "error": "WiFi 비밀번호는 8자 이상, 63자 이하여야 합니다."}), 400

        if platform.system() == "Linux":
            try:
                PROFILE_NAME = "Pathfinder-Client"
                subprocess.run(["sudo", "nmcli", "connection", "delete", PROFILE_NAME], capture_output=True)

                if password and password.strip():
                    add_command = [
                        "sudo", "nmcli", "connection", "add",
                        "type", "wifi",
                        "con-name", PROFILE_NAME,
                        "ifname", "wlan0",
                        "ssid", ssid,
                        "wifi-sec.key-mgmt", "wpa-psk",
                        "wifi-sec.psk", password,
                        "connection.autoconnect", "yes",
                    ]
                else:
                    add_command = [
                        "sudo", "nmcli", "connection", "add",
                        "type", "wifi",
                        "con-name", PROFILE_NAME,
                        "ifname", "wlan0",
                        "ssid", ssid,
                        "connection.autoconnect", "yes",
                    ]
                subprocess.run(add_command, check=True, text=True, capture_output=True, timeout=15)

                robot_id = get_robot_id()
                _write_robot_config(robot_id, get_default_robot_name())

                subprocess.run("echo 'MODE=CLIENT' | sudo tee /etc/pf_env", shell=True, check=True)

                return jsonify({
                    "success": True,
                    "message": "WiFi 정보 저장 성공! 클라이언트 모드로 전환합니다.",
                    "robot_name": get_default_robot_name(),
                })
            except Exception as e:
                return jsonify({"success": False, "error": str(e) + "(WIFI SETUP ERROR)"}), 500
            finally:
                subprocess.Popen(["sudo", "/usr/local/bin/pf-netmode-bookworm.sh"])
        else:
            time.sleep(2)
            return jsonify({"success": True, "robot_name": "Testbot", "message": "Linux 환경이 아닙니다."})

    except Exception as e:
        return jsonify({"success": False, "error": str(e) + "(API ERROR)"}), 500


if __name__ == "__main__":
    oled.show_qr_on_oled(get_default_robot_name)
    app.run(host="0.0.0.0", port=5000, debug=False)
