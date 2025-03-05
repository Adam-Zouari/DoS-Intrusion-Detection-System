import React from 'react';

function PacketTable({ packets, onSelectPacket, selectedPacket }) {
    return (
        <div style={{
            width: '100%',
            overflow: 'hidden',
            maxHeight: '25%',
            overflowY: 'auto',
            backgroundColor: '#f8f8f8',
            boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
            fontFamily: 'Arial, sans-serif'
        }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                    <tr style={{ backgroundColor: '#F2F2F2', color: '#000', fontWeight: 'bold' }}>
                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Time</th>
                        <th style={{ padding: '12px 25px', borderBottom: '1px solid #ddd' }}>Source</th>
                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Destination</th>
                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Protocol</th>
                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Length</th>
                    </tr>
                </thead>
                <tbody>
                    {packets.map((packet, index) => (
                        <tr
                            key={index}
                            style={{
                                backgroundColor: packet === selectedPacket ? '#cceeff' : 'transparent',
                                cursor: 'pointer',
                                transition: 'background-color 0.3s ease',
                            }}
                            onClick={() => onSelectPacket(packet)}
                            onMouseOver={(e) => (e.currentTarget.style.backgroundColor = '#e6f7ff')}
                            onMouseOut={(e) => (e.currentTarget.style.backgroundColor = packet === selectedPacket ? '#cceeff' : 'transparent')}
                        >
                            <td style={{ padding: '5px 14px', borderBottom: '1px solid #ddd', color: '#333' }}>{packet.time}</td>
                            <td style={{ padding: '5px 15px', borderBottom: '1px solid #ddd', color: '#333' }}>{packet.source}</td>
                            <td style={{ padding: '5px 15px', borderBottom: '1px solid #ddd', color: '#333' }}>{packet.destination}</td>
                            <td style={{ padding: '5px 15px', borderBottom: '1px solid #ddd', color: '#333' }}>{packet.protocol}</td>
                            <td style={{ padding: '5px 15px', borderBottom: '1px solid #ddd', color: '#333' }}>{packet.length}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export default PacketTable;
