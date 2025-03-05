import React from 'react';

function NotificationButton({ notification, isActive, onClick }) {
    const buttonStyle = {
        padding: isActive ? '40px' : '20px',
        borderRadius: '10px',
        backgroundColor: notification.color,
        color: 'white',
        textAlign: 'center',
        boxShadow: '2px 2px 4px rgba(0, 0, 0, 0.1)',
        fontSize: '14px',
        cursor: 'pointer',
        transition: 'padding 0.3s ease',
    };

    return (
        <div style={buttonStyle} onClick={onClick}>
            {notification.text}
            {isActive && (
                <div style={{ marginTop: '20px', fontSize: '12px' }}>
                    {/* Show detailed information about the notification here */}
                    <p>{notification.details}</p>
                </div>
            )}
        </div>
    );
}

export default NotificationButton;

