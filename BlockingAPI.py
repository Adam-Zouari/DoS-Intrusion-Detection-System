from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Assume this is a global variable holding the blocked MAC addresses
blocked_macs = []

@app.route('/unblock/<mac>', methods=['POST'])
def unblock_mac(mac):
    if mac in blocked_macs:
        blocked_macs.remove(mac)
        response = jsonify(message=f"L'adresse MAC {mac} a été débloquée.")
        response.status_code = 200  # HTTP 200 OK
        return response
    else:
        response = jsonify(error=f"L'adresse MAC {mac} n'était pas bloquée.")
        response.status_code = 404  # HTTP 404 Not Found
        return response

@app.route('/block/<mac>', methods=['POST'])
def block_mac_route(mac):
    if mac not in blocked_macs:
        blocked_macs.append(mac)
        response = jsonify(message=f"L'adresse MAC {mac} a été bloquée.")
        response.status_code = 200  # HTTP 200 OK
        return response
    else:
        response = jsonify(error=f"L'adresse MAC {mac} est déjà bloquée.")
        response.status_code = 409  # HTTP 409 Conflict
        return response


if __name__ == '__main__':
    app.run(debug=True)
