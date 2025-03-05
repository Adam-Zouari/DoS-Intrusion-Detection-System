import ButtonGroup from "./Buttons";
import logo from '../assets/Logo.png';

function Banner({ setActiveView, activeView }) {
    const bannerStyle = {
        padding: '10px',
        backgroundColor: 'rgba(18, 50, 70, 1)',
        color: 'white',
        height: '100px',
        width: '100%',
    };

   {/* const imageStyle = {
        height: '70px',
    };*/}

    return (
        <div style={bannerStyle}>
            {/*<img src={logo} alt="Logo" style={imageStyle} />*/}
            <ButtonGroup setActiveView={setActiveView} activeView={activeView} />
        </div>
    );
}

export default Banner;

