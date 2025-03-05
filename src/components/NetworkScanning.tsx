import React, { useState, useEffect, useRef } from 'react';
import PacketTable from './PacketTable';
import PacketDetails from './PacketDetails';
import Filter from './Filter';
import Banner from './SecondaryBanner';

const packetsData = [
    { time: '08:45:55', source: '192.168.1.1', destination: '192.168.1.16', protocol: 'TCP', length: '54', protocolInfo: 'TCP Segment', sourcePort: 443, destinationPort: 80 },
    { time: '08:50:30', source: '192.168.1.1', destination: '192.168.1.16', protocol: 'TCP', length: '80', protocolInfo: 'TCP Segment', sourcePort: 443, destinationPort: 80 },
    { time: '08:55:12', source: '192.168.1.16', destination: '192.168.1.1', protocol: 'TCP', length: '200', protocolInfo: 'TCP Segment', sourcePort: 443, destinationPort: 80 },
    { time: '09:00:00', source: '192.168.1.2', destination: '192.168.1.17', protocol: 'UDP', length: '60', protocolInfo: 'UDP Datagram', sourcePort: 1234, destinationPort: 5678 },
    { time: '09:05:45', source: '192.168.1.3', destination: '192.168.1.18', protocol: 'ICMP', length: '64', protocolInfo: 'ICMP Echo Request', sourcePort: null, destinationPort: null },
    { time: '09:10:30', source: '192.168.1.4', destination: '192.168.1.19', protocol: 'TCP', length: '100', protocolInfo: 'TCP Segment', sourcePort: 22, destinationPort: 80 },
    { time: '09:15:15', source: '192.168.1.5', destination: '192.168.1.20', protocol: 'TCP', length: '150', protocolInfo: 'TCP Segment', sourcePort: 3306, destinationPort: 3306 },
    { time: '09:20:00', source: '192.168.1.6', destination: '192.168.1.21', protocol: 'UDP', length: '85', protocolInfo: 'UDP Datagram', sourcePort: 9090, destinationPort: 8080 },
    { time: '09:25:45', source: '192.168.1.7', destination: '192.168.1.22', protocol: 'TCP', length: '75', protocolInfo: 'TCP Segment', sourcePort: 443, destinationPort: 80 },
    { time: '09:30:30', source: '192.168.1.8', destination: '192.168.1.23', protocol: 'ICMP', length: '56', protocolInfo: 'ICMP Echo Reply', sourcePort: null, destinationPort: null },
    { time: '09:35:15', source: '192.168.1.9', destination: '192.168.1.24', protocol: 'UDP', length: '70', protocolInfo: 'UDP Datagram', sourcePort: 6000, destinationPort: 7000 },
    { time: '09:40:00', source: '192.168.1.10', destination: '192.168.1.25', protocol: 'TCP', length: '120', protocolInfo: 'TCP Segment', sourcePort: 8080, destinationPort: 443 },
    { time: '09:45:45', source: '192.168.1.11', destination: '192.168.1.26', protocol: 'TCP', length: '90', protocolInfo: 'TCP Segment', sourcePort: 21, destinationPort: 80 },
    { time: '09:50:30', source: '192.168.1.12', destination: '192.168.1.27', protocol: 'UDP', length: '95', protocolInfo: 'UDP Datagram', sourcePort: 1000, destinationPort: 2000 },
    { time: '09:55:15', source: '192.168.1.13', destination: '192.168.1.28', protocol: 'ICMP', length: '72', protocolInfo: 'ICMP Echo Request', sourcePort: null, destinationPort: null }
];


function NetworkScanning() {
    const [selectedPacket, setSelectedPacket] = useState(null);
    const [filteredPackets, setFilteredPackets] = useState(packetsData);
    const detailsRef = useRef(null);

    const handleSelectPacket = (packet) => {
        setSelectedPacket(packet);
    };

    const handleFilterChange = (filter) => {
        const [key, value] = filter.split('=');
        
        // Basic validation for key and value
        if (!key || !value) {
            setFilteredPackets(packetsData);
            return;
        }

        let filtered = packetsData;
        
        switch (key) {
            case 'ip.src':
                filtered = packetsData.filter(packet => packet.source === value);
                break;
            case 'ip.dest':
                filtered = packetsData.filter(packet => packet.destination === value);
                break;
            case 'ip.time':
                filtered = packetsData.filter(packet => packet.time === value);
                break;
            case 'ip.length':
                filtered = packetsData.filter(packet => packet.length === value);
                break;
            // Add more cases as needed for other filtering criteria
            default:
                filtered = packetsData;
                break;
        }

        setFilteredPackets(filtered);
    };

    useEffect(() => {
        // Function to handle clicks outside of the detailsRef
        const handleClickOutside = (event) => {
            if (detailsRef.current && !detailsRef.current.contains(event.target)) {
                setSelectedPacket(null);
            }
        };

        // Attach the event listener
        document.addEventListener('mousedown', handleClickOutside);

        // Clean up the event listener on component unmount
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    return (
        <div style={{
            position: 'relative',
            top: '10px',
            left: '10.1%',
            width: '44%',
            height: '83.5%',
            backgroundColor: 'white',
            borderRadius: '20px',
            boxSizing: 'border-box',
            zIndex: 1,  // Set a positive z-index or remove entirely
        }}>
            <Banner message="Network Scanning" />
            <Filter onFilterChange={handleFilterChange} placeholderText="e.g., ip.src=192.168.1.1" />
            <PacketTable packets={filteredPackets} onSelectPacket={handleSelectPacket} />
            {selectedPacket && (
                <div ref={detailsRef}>
                    <PacketDetails packet={selectedPacket} />
                </div>
            )}
        </div>
    );
}

export default NetworkScanning;