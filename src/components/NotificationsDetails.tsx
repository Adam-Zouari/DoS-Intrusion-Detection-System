import { useState, useEffect } from 'react';
import Banner from './SecondaryBanner';
import NotificationButton from './NotificationButton';

const notifications = [
    { id: 1, text: 'A Banned machine has entered the network', color: 'rgba(18, 50, 70, 1)', details: 'The machine with MAC address 00:1A:2B:3C:4D:5E has been banned and was detected on the network at 10:23 AM.' },
    { id: 2, text: 'An IP address is sending a lot of packets', color: 'rgba(28, 85, 120, 1)', details: 'The IP address 192.168.0.101 is generating an unusual amount of network traffic, indicating a potential issue.'},
    { id: 3, text: 'A New Machine has joined the network!', color: 'rgba(21, 129, 195, 1)', details: 'A new device with MAC address 00:6D:8E:9F:AB:CD has connected to the network at 11:05 AM.' },
    { id: 4, text: 'The system is restarting soon!', color: 'rgba(37, 172, 255, 1)', details: 'The network monitoring system will undergo a scheduled restart at 12:00 PM. Please save your work.' },
];

function NotificationsDetails() {
    const [activeNotification, setActiveNotification] = useState(null);

    const handleNotificationClick = (notification) => {
        setActiveNotification(notification.id === activeNotification ? null : notification);
    };

    // Click outside to reset
    useEffect(() => {
        const handleClickOutside = (e) => {
            if (!e.target.closest('.notification-container')) {
                setActiveNotification(null);
            }
        };

        document.addEventListener('click', handleClickOutside);
        return () => {
            document.removeEventListener('click', handleClickOutside);
        };
    }, []);

    return (
        <div
            style={{
                position: 'relative',
                top: 10,
                left: 20,
                width: '30%',
                height: '83%',
                backgroundColor: 'white',
                borderRadius: '10px',
                boxSizing: 'border-box',
                zIndex: 1,
                boxShadow: '4px 4px 8px rgba(0, 0, 0, 0.1)',
                overflowY: 'auto',
            }}
        >
            <Banner />
            <div
                className="notification-container"
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '30px',
                    marginTop: '20px',
                    padding: '5px',
                }}
            >
                {notifications.map((notification) => (
                    <NotificationButton
                        key={notification.id}
                        notification={notification}
                        isActive={activeNotification && activeNotification.id === notification.id}
                        onClick={(e) => {
                            e.stopPropagation(); // Prevent click outside detection
                            handleNotificationClick(notification);
                        }}
                    />
                ))}
            </div>
        </div>
    );
}

export default NotificationsDetails;
