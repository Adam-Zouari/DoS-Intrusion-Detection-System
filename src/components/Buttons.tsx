function ButtonGroup({ setActiveView, activeView }) {
    const buttonGroupStyle = {
        display: 'flex',
        justifyContent: 'center',
        marginTop: '-30px',
        padding: '50px'
    };

    return (
        <div style={buttonGroupStyle}>
            <button
                className={`btn ${activeView === 'dashboard' ? 'btn-primary' : 'btn-outline-secondary'}`}
                onClick={() => setActiveView('dashboard')}
            >
                Dashboard
            </button>
            <button
                className={`btn ${activeView === 'machines' ? 'btn-primary' : 'btn-outline-secondary'}`}
                onClick={() => setActiveView('machines')}
                style={{ marginLeft: '30px' }}
            >
                Machines
            </button>
        </div>
    );
}

export default ButtonGroup;
