import React, { useState } from 'react';

function Filter({ onFilterChange, placeholderText }) {
    const [filterInput, setFilterInput] = useState('');

    const filterStyle = {
        display: 'flex',
        alignItems: 'center',
        padding: '10px',
        backgroundColor: 'rgba(217, 217, 217, 1)',
        boxShadow: '0px 2px 5px rgba(0, 0, 0, 0.1)',
    };

    const labelStyle = {
        marginRight: '10px',
        fontSize: '16px',
        color: 'rgba(18, 50, 70, 1)',
        fontWeight: 'bold',
    };

    const inputStyle = {
        padding: '8px 12px',
        fontSize: '16px',
        borderRadius: '5px',
        border: '1px solid rgba(18, 50, 70, 0.3)',
        outline: 'none',
        backgroundColor: 'white',
        color: 'rgba(18, 50, 70, 1)',
        boxShadow: '0px 2px 5px rgba(0, 0, 0, 0.1)',
        marginRight: '10px',
        flex: 1,
    };

    const buttonStyle = {
        padding: '8px 12px',
        fontSize: '16px',
        borderRadius: '5px',
        border: '1px solid rgba(18, 50, 70, 0.3)',
        backgroundColor: 'rgba(18, 50, 70, 1)',
        color: 'white',
        cursor: 'pointer',
        boxShadow: '0px 2px 5px rgba(0, 0, 0, 0.1)',
    };

    const handleChange = (event) => {
        setFilterInput(event.target.value);
    };

    const handleSubmit = (event) => {
        event.preventDefault();
        onFilterChange(filterInput);
    };

    return (
        <div style={filterStyle}>
            <form onSubmit={handleSubmit} style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
                <label htmlFor="filter" style={labelStyle}>Filter by:</label>
                <input 
                    id="filter" 
                    type="text" 
                    value={filterInput} 
                    onChange={handleChange} 
                    placeholder={placeholderText} 
                    style={inputStyle} 
                />
                <button type="submit" style={buttonStyle}>Apply Filter</button>
            </form>
        </div>
    );
}

export default Filter;


