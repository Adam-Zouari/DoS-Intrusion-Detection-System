import { useState } from 'react';
import ConnectionTimeChart from './ConnectionTimeChart';
import Banner from './MainBanner';
import TotalLengthOfPacketsHistogram from './Histogram';
import NetworkScanning from './NetworkScanning';
import Notifications from './Notifications';
import NotificationsDetails from './NotificationsDetails';
import MachinesDetails from './MachinesDetails';

function Dashboard() {
    const [activeView, setActiveView] = useState('dashboard'); // State to track active view

    const dashboardStyle = {
        height: '100vh', // Full viewport height
        width: '100vw', // Full viewport width
        display: 'flex',
        flexDirection: 'row', // Arrange children horizontally
        flexWrap: 'nowrap', // Allow wrapping to the next line
        boxSizing: 'border-box',
    };

    const chartsContainerStyle = {
        display: 'flex',
        flexDirection: 'column', // Arrange children vertically
        marginTop:'10px',
        marginLeft: '10px' ,
    };


    return (
        <>
            <Banner setActiveView={setActiveView} activeView={activeView} />
            <div style={dashboardStyle}>
                    {activeView === 'dashboard' && (
                        <>
                            <div style={chartsContainerStyle}>
                                <ConnectionTimeChart />
                                <TotalLengthOfPacketsHistogram />
                            </div>
                            <NetworkScanning />
                            <Notifications />
                        </>
                    )}
                    {activeView === 'machines' && (
                        <>
                            <MachinesDetails />
                            <NotificationsDetails /> {/* Notifications for Machines view */}
                        </>
                    )}
                </div>
        </>
    );
}

export default Dashboard;

