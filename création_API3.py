from flask import Flask, request, abort

app = Flask(__name__)

# Adresse IP autorisée
AUTHORIZED_IP = '192.168.1.100'  # Remplacez par l'adresse IP que vous souhaitez autoriser

@app.before_request
def limit_remote_addr():
    if request.remote_addr != AUTHORIZED_IP:
        abort(403)  # Refuse l'accès avec une erreur 403 Forbidden

@app.route('/')
def index():
    return "Bienvenue, votre adresse IP est autorisée!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
