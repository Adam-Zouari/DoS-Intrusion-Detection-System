from flask import Flask, request, jsonify
import nmap


app = Flask(__name__)

# Instance de PortScanner globale
nm = None  # Variable globale pour stocker l'instance de PortScanner

def scan_network(network_range):
    global nm  
    nm = nmap.PortScanner()  
    nm.scan(hosts=network_range, arguments='-sP')  

@app.route('/start_scan', methods=['POST'])
def start_scan():
    data= request.get_json()
    network_range= data.get('network_range', '')

    if not network_range:
        return jsonify ({"error": "la plage IP est requise"}),400
    
    scan_network(network_range)
    return jsonify({"message": f"scan démaré pour la plage IP{network_range}"}),200

@app.route('/network_data', methods=['GET'])

def get_network_data (): 
    if nm is None:
        return jsonify({"error": "aucun scan effecté"}),
    network_data={}
    for host in nm.all_hosts():
        # Get the hostnames in the required format
        hostnames = [{'name': hostname['name'], 'type': hostname['type']} for hostname in nm[host].hostnames()]#supposons q'une adresse IP a plus que nom
        
        # Get the addresses in the required format
        addresses = {
            'ipv4': nm[host]['addresses'].get('ipv4', ''),
            'mac': nm[host]['addresses'].get('mac', '')
        }
        
        # Get the vendor information based on MAC address
        vendor = {addresses['mac']: nm[host]['vendor'].get(addresses['mac'], '')}
        # Get the status information
        status = {
            'state': nm[host].state(),
            'reason': nm[host]['status']['reason']
        }
        
        # Add the host information to the network_data dictionary
        if status=={'state': "up"}:
           network_data[host] = {
            'hostnames': hostnames,
            'addresses': addresses,
            'vendor': vendor,
            'status': status,
            'services':nm[host].all_tcp(),
        }
    
    return  jsonify(network_data),200  # Return the dictionary containing the network information


if __name__=='__main__':
    app.run('0.0.0.0', port =5000)

