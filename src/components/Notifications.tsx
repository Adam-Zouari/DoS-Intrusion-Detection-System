import Banner from './SecondaryBanner';

const notifications = [
    { id: 1, text: 'Attack Detected!', color: 'rgba(18, 50, 70, 1)' },
    { id: 2, text: 'Unusual Traffic Detected!', color: 'rgba(28, 85, 120, 1)' },
    { id: 3, text: 'New Machine Detected!', color: 'rgba(21, 129, 195, 1)' },
    { id: 4, text: 'Restarting!', color: 'rgba(37, 172, 255, 1)' },
];

function Notifications() {
    return (
        <div style={{
            position: 'relative',
            left: '6.8%', 
            width: '20.4%',
            marginTop: '10px',
            marginLeft: '3.8%',
            height: '83.5%',
            backgroundColor: 'white',
            borderRadius: '20px',
            boxSizing: 'border-box',
            zIndex: 1,  
            boxShadow: '4px 4px 8px rgba(0, 0, 0, 0.1)',
        }}>
            <Banner message="Notifications" />
            {/* Notifications List */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '30px',marginTop:'20px',padding:'5px' }}>
                {notifications.map(notification => (
                    <div
                        key={notification.id}
                        style={{
                            padding: '20px',
                            borderRadius: '10px',
                            backgroundColor: notification.color,
                            color: 'white',
                            textAlign: 'center',
                            boxShadow: '2px 2px 4px rgba(0, 0, 0, 0.1)',
                            fontSize: '14px',
                        }}
                    >
                        {notification.text}
                    </div>
                ))}
            </div>
        </div>
    );
}

export default Notifications;
