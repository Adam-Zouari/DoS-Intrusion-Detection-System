import  { useState } from 'react';

function BlockButton({ macAddress }) {
    const [isBlocked, setIsBlocked] = useState(false);
    const [loading, setLoading] = useState(false);
   
  

    const handleClick = async () => {
        setLoading(true);
        const action = isBlocked ? 'unblock' : 'block';
        try {
            const response = await fetch(`http://127.0.0.1:5000/${action}/${macAddress}`, {
                method: 'POST',
            });
            if (response.ok) {
                setIsBlocked(!isBlocked); // Toggle the blocked status
            } else {
                const data = await response.json();
                console.error('Error:', data.error);
            }
        } catch (error) {
            console.error(`Error trying to ${action} MAC address:`, error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <button
            onClick={handleClick}
            disabled={loading}
            className={`btn btn-outline-${isBlocked ? 'secondary' : 'primary'}`}
            style={{ 
                padding: '8px 16px', 
                minWidth: '140px', // Set a fixed minimum width
                fontSize: '16px'  // Ensure a consistent font size
            }}
        >
            {loading ? 'Processing...' : isBlocked ? 'Unblock' : 'Block'}
        </button>
    );
}

export default BlockButton;

