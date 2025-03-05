import { useState } from 'react';
import MachinesTable from './MachinesTable';
import Filter from './Filter';
import Banner from './SecondaryBanner';

const machinesData = [
    { macAddress: '00:1A:2B:3C:4D:5E', status: 'Active', totalConnectionTime: '5 hours', totalLengthOfPackets: '1024 bytes', information: 'WindowsPC', block: 'No' },
    { macAddress: '00:6D:8E:9F:AB:CD', status: 'Inactive', totalConnectionTime: '2 hours', totalLengthOfPackets: '512 bytes', information: 'Android', block: 'Yes' },
    { macAddress: '00:9F:3D:4C:5E:AB', status: 'Active', totalConnectionTime: '8 hours', totalLengthOfPackets: '2048 bytes', information: 'Switch', block: 'No' },
    { macAddress: '00:AB:12:CD:34:EF', status: 'Active', totalConnectionTime: '1 hour', totalLengthOfPackets: '256 bytes', information: 'SmartTV', block: 'No' },
    { macAddress: '00:CD:34:EF:12:AB', status: 'Inactive', totalConnectionTime: '3 hours', totalLengthOfPackets: '768 bytes', information: 'Printer', block: 'Yes' },
    { macAddress: '00:EF:12:AB:34:CD', status: 'Active', totalConnectionTime: '4 hours', totalLengthOfPackets: '1024 bytes', information: 'Router', block: 'No' },
    { macAddress: '00:AB:CD:12:EF:34', status: 'Active', totalConnectionTime: '6 hours', totalLengthOfPackets: '1536 bytes', information: 'WindowsPC', block: 'No' },
    { macAddress: '00:34:EF:AB:12:CD', status: 'Inactive', totalConnectionTime: '7 hours', totalLengthOfPackets: '2048 bytes', information: 'Laptop', block: 'Yes' },
    { macAddress: '00:EF:CD:34:AB:12', status: 'Active', totalConnectionTime: '2 hours', totalLengthOfPackets: '512 bytes', information: 'Android', block: 'No' },
    { macAddress: '00:12:AB:CD:EF:34', status: 'Inactive', totalConnectionTime: '1 hour', totalLengthOfPackets: '256 bytes', information: 'SmartTV', block: 'Yes' },
    { macAddress: '00:AB:34:EF:12:CD', status: 'Active', totalConnectionTime: '3 hours', totalLengthOfPackets: '768 bytes', information: 'Switch', block: 'No' },
    { macAddress: '00:CD:EF:12:AB:34', status: 'Active', totalConnectionTime: '5 hours', totalLengthOfPackets: '1024 bytes', information: 'Router', block: 'No' },
    { macAddress: '00:EF:34:AB:CD:12', status: 'Inactive', totalConnectionTime: '4 hours', totalLengthOfPackets: '512 bytes', information: 'Printer', block: 'Yes' },
    { macAddress: '00:12:34:AB:CD:EF', status: 'Active', totalConnectionTime: '6 hours', totalLengthOfPackets: '1536 bytes', information: 'Laptop', block: 'No' },
    { macAddress: '00:AB:CD:EF:34:12', status: 'Inactive', totalConnectionTime: '2 hours', totalLengthOfPackets: '256 bytes', information: 'Android', block: 'Yes' },
    { macAddress: '00:34:AB:CD:EF:12', status: 'Active', totalConnectionTime: '7 hours', totalLengthOfPackets: '2048 bytes', information: 'WindowsPC', block: 'No' }
];



function MachinesDetails() {
    const [filteredMachines, setFilteredMachines] = useState(machinesData);

    const handleFilterChange = (filter) => {
        const [key, value] = filter.split('=');

        // Basic validation for key and value
        if (!key || !value) {
            setFilteredMachines(machinesData);
            return;
        }

        let filtered = machinesData;

        switch (key) {
            case 'mac':
                filtered = machinesData.filter(machine => machine.macAddress === value);
                break;
            case 'status':
                filtered = machinesData.filter(machine => machine.status === value);
                break;
            // Add more cases as needed for other filtering criteria
            default:
                filtered = machinesData;
                break;
        }

        setFilteredMachines(filtered);
    };

    return (
        <div style={{
            position: 'relative',
            top: 10,
            left: 10,
            width: '68%',
            height: '83%',
            backgroundColor: 'white',
            borderRadius: '20px',
            boxSizing: 'border-box',
            zIndex: 1,  // Set a positive z-index or remove entirely
        }}>
            <Banner message="Machines' Details" />
            <Filter onFilterChange={handleFilterChange} placeholderText="e.g., mac=00:14:22:01:23:45" />
            <MachinesTable machines={filteredMachines} />
        </div>
    );
}

export default MachinesDetails;
