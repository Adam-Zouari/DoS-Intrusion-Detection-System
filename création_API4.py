from flask import Flask, jsonify, request
from scapy.all import sniff, IP, TCP, UDP
from collections import defaultdict
import time
import threading

app = Flask(__name__)

# Dictionnaires pour stocker les informations nécessaires
ip_packet_count = defaultdict(int)
ip_port_usage = defaultdict(set)
port_scan_attempts = defaultdict(int)
ddos_suspects = defaultdict(int)
alerts = []

# Définition des ports considérés comme typiques (HTTP, HTTPS, FTP, SSH, etc.)
typical_ports = {80, 443, 21, 22, 23, 25, 110, 143, 53, 445, 3389}

# Fonction de traitement des paquets capturés
def packet_handler(packet):
    global alerts
    if packet.haslayer(IP):
        ip_src = packet[IP].src
        ip_dst = packet[IP].dst
        
        ip_packet_count[ip_src] += 1 
        
        if packet.haslayer(TCP) or packet.haslayer(UDP):
            if packet.haslayer(TCP):
                dport = packet[TCP].dport
            else:
                dport = packet[UDP].dport

            ip_port_usage[ip_src].add(dport)
            if len(ip_port_usage[ip_src]) > 10:
                port_scan_attempts[ip_src] += 1
                alert = f"[ALERTE] Scan de ports détecté: IP suspecte {ip_src} scanne {len(ip_port_usage[ip_src])} ports"
                alerts.append(alert)

            if dport not in typical_ports:
                alert = f"[ALERTE] Connexion à un port atypique: IP {ip_src} se connecte au port {dport}"
                alerts.append(alert)

        if ip_packet_count[ip_src] > 1000:
            ddos_suspects[ip_src] += 1
            alert = f"[ALERTE] Attaque DDoS suspectée: IP {ip_src} a envoyé plus de 1000 paquets"
            alerts.append(alert)

        if ip_packet_count[ip_src] > 500 and ip_packet_count[ip_dst] < 10:
            alert = f"[ALERTE] Trafic inhabituel: IP {ip_src} envoie beaucoup de paquets, peu de réponses de {ip_dst}"
            alerts.append(alert)

# Fonction principale pour capturer les paquets
def start_sniffing():
    sniff(prn=packet_handler, store=False, timeout=60)

# Route pour démarrer la capture des paquets
@app.route('/start_sniffing', methods=['POST'])
def start_sniffing_route():
    global alerts
    alerts = []
    threading.Thread(target=start_sniffing).start()
    return jsonify({"message": "Capture des paquets démarrée"}), 200

# Route pour récupérer les alertes
@app.route('/alerts', methods=['GET'])
def get_alerts():
    return jsonify({"alerts": alerts}), 200

# Réinitialisation des compteurs toutes les 10 minutes pour éviter la surcharge mémoire
def reset_counters():
    global ip_packet_count, ip_port_usage, port_scan_attempts, ddos_suspects
    while True:
        time.sleep(600)
        ip_packet_count.clear()
        ip_port_usage.clear()
        port_scan_attempts.clear()
        ddos_suspects.clear()

if __name__ == "__main__":
    # Lancer le thread de réinitialisation des compteurs
    threading.Thread(target=reset_counters).start()
    # Démarrer l'application Flask
    app.run(host='0.0.0.0', port=5000)
