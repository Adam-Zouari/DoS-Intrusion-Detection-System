
function Banner({ message = "Notifications" }) {
    const bannerStyle = {
        borderTopLeftRadius: '10px', 
        borderTopRightRadius: '10px', 
        padding: '15px',
        backgroundColor: 'rgba(18, 50, 70, 1)',
        color: 'white',
        height: '100px',
        width: '100%',
        display: 'flex', // Use flexbox to center the content
        alignItems: 'center', // Vertically center
        justifyContent: 'center', // Horizontally center
        fontSize: '24px', // Make the font bigger
        fontWeight: 'bold', // Make the font bold
        boxShadow: '0px 2px 5px rgba(0, 0, 0, 0.1)',
    };

    return (
        <div style={bannerStyle}>
            {message}
        </div>
    );
}

export default Banner;

