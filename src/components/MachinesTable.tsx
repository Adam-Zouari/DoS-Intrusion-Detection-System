import BlockButton from './BlockButton';  // Import the BlockButton component

function MachinesTable({ machines }) {
    return (
        <div style={{
            width: '100%',
            maxHeight: '74%',  // Set a maximum height for the container
            overflowY: 'auto',   // Enable vertical scrolling
            backgroundColor: '#f8f8f8',
            boxShadow: '0 2px 4px rgba(0, 0, 0, 0.1)',
            fontFamily: 'Arial, sans-serif',
            borderRadius: '10px'
        }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                    <tr style={{ backgroundColor: '#F2F2F2', color: '#000', fontWeight: 'bold' }}>
                        <th style={{ padding: '12px 35px', borderBottom: '1px solid #ddd' }}>Mac Address</th>
                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Status</th>
                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Total Connection Time</th>
                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Total Length of Packets</th>
                        <th style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>Information</th>
                        <th style={{ padding: '12px 64px', borderBottom: '1px solid #ddd' }}>Block</th>
                    </tr>
                </thead>
                <tbody>
                    {machines.map((machine, index) => (
                        <tr key={index}>
                            <td style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>{machine.macAddress}</td>
                            <td style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>{machine.status}</td>
                            <td style={{ padding: '12px 65px', borderBottom: '1px solid #ddd' }}>{machine.totalConnectionTime}</td>
                            <td style={{ padding: '12px 65px', borderBottom: '1px solid #ddd' }}>{machine.totalLengthOfPackets}</td>
                            <td style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>{machine.information}</td>
                            <td style={{ padding: '12px 15px', borderBottom: '1px solid #ddd' }}>
                                <BlockButton macAddress={machine.macAddress} /> 
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export default MachinesTable;


