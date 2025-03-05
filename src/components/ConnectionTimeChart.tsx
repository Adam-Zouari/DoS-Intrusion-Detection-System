import React from 'react';
import { PieChart, Pie, Cell, Tooltip, Legend } from 'recharts';

const data = [
    { name: '2C:54:91:88:C9:E3', value: 35, color: 'rgba(18, 50, 70, 1)' },
    { name: '00:1A:2B:3C:4D:5E', value: 25, color: 'rgba(28, 85, 120, 1)' },
    { name: 'A0:CE:C8:01:23:45', value: 20, color: 'rgba(21, 129, 195, 1)' },
    { name: '08:00:27:12:34:56', value: 15, color: 'rgba(37, 172, 255, 1)' },
];

const total = data.reduce((sum, entry) => sum + entry.value, 0);

const formattedData = data.map(entry => ({
    ...entry,
    percentage: ((entry.value / total) * 100).toFixed(1) + '%'
}));

function renderCustomizedLabel({ cx, cy, midAngle, innerRadius, outerRadius, value }) {
    const radius = (outerRadius + innerRadius) / 2;
    const x = cx + radius * Math.cos(-midAngle * Math.PI / 180);
    const y = cy + radius * Math.sin(-midAngle * Math.PI / 180);

    return (
        <text x={x} y={y} fill="#fff" textAnchor="middle" dominantBaseline="central">
            {value}%
        </text>
    );
}

function ConnectionTimeChart() {
    return (
            <div style={{
                position :'relative',
                width: '140%',
                height: '50%', 
                backgroundColor: 'white',
                borderRadius: '20px', // Optional: Rounded corners
                padding: '20px', // Adjust padding to make space for label and pie chart
                boxSizing: 'border-box', // Ensure padding is included in the width and height
                zIndex: -1, // Ensure background is behind the content
                boxShadow: '4px 4px 8px rgba(0, 0, 0, 0.1)',
            }}>
                {/* Container for label and pie chart */}
                <div style={{ textAlign: 'center', marginBottom: '10px' }}>
                    {/* Label at the top */}
                    <div style={{
                        fontSize: '16px',
                        fontWeight: 'bold',
                        color: '#333', // Optional: Adjust label color
                    }}>
                        Machines with the highest connection time
                    </div>
                </div>

                {/* Pie Chart */}
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                    <PieChart width={300} height={190}>
                        <Pie
                            data={formattedData}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            outerRadius={80} // Adjust radius to fit the pie chart size
                            label={renderCustomizedLabel} // Apply custom label function
                            labelLine={false} // Remove lines from the pie chart
                        >
                            {formattedData.map((entry, index) => (
                                <Cell
                                    key={`cell-${index}`}
                                    fill={entry.color}
                                    stroke={entry.color}
                                />
                            ))}
                        </Pie>
                        <Tooltip />
                        <Legend 
                            layout="vertical"
                            verticalAlign="" // Align vertically to the top
                            wrapperStyle={{ marginTop: 180 }} // Adjust marginTop to move legend down
                        />
                    </PieChart>
                </div>
            </div>
    );
}

export default ConnectionTimeChart;
