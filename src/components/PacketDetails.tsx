import React from 'react';

function PacketDetails({ packet }) {
    if (!packet) {
        return <div style={{ padding: '20px', color: 'rgba(18, 50, 70, 0.7)' }}>Select a packet to see its details</div>;
    }

    const detailsContainerStyle = {
        padding: '20px',
        boxShadow: '0px 4px 8px rgba(0, 0, 0, 0.1)',

    };

    const headerStyle = {
        marginBottom: '10px',
        fontSize: '20px',
        color: 'rgba(18, 50, 70, 1)',
        borderBottom: '2px solid rgba(18, 50, 70, 0.2)',
        paddingBottom: '10px',
    };

    const rowStyle = {
        display: 'flex',
        justifyContent: 'space-between',
        flexWrap: 'wrap',  // This ensures the items wrap if they don't fit in one line
        marginBottom: '15px',
    };

    const itemStyle = {
        flex: '1 1 20%',  // Each item will take up 20% of the row, allowing 5 items per row
        marginRight: '10px', // Margin between items
        marginBottom: '10px', // Margin at the bottom in case they wrap
        fontSize: '16px',
        color: 'rgba(18, 50, 70, 0.8)',
    };

    const listStyle = {
        paddingLeft: '20px',
        marginTop: '10px',
        color: 'rgba(18, 50, 70, 0.8)',
    };

    return (
        <div style={detailsContainerStyle}>
            <h3 style={headerStyle}>Packet Details</h3>
            <div style={rowStyle}>
                <div style={itemStyle}><strong>Time:</strong> {packet.time}</div>
                <div style={itemStyle}><strong>Source:</strong> {packet.source}</div>
                <div style={itemStyle}><strong>Destination:</strong> {packet.destination}</div>
                <div style={itemStyle}><strong>Protocol:</strong> {packet.protocol}</div>
                <div style={itemStyle}><strong>Length:</strong> {packet.length} bytes</div>
            </div>
            <p style={{ fontSize: '16px', color: 'rgba(18, 50, 70, 0.8)', marginTop: '15px' }}><strong>Additional Info:</strong></p>
            <ul style={listStyle}>
                <li><strong>Protocol Info:</strong> {packet.protocolInfo}</li>
                <li><strong>Source Port:</strong> {packet.sourcePort}</li>
                <li><strong>Destination Port:</strong> {packet.destinationPort}</li>
            </ul>
        </div>
    );
}

export default PacketDetails;

