import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid, Cell, LabelList } from 'recharts';

const data = [
    { name: '2C:54:91:88:C9:E3', value: 3200, color: 'rgba(18, 50, 70, 1)' },
    { name: '00:1A:2B:3C:4D:5E', value: 2700, color: 'rgba(28, 85, 120, 1)' },
    { name: 'A0:CE:C8:01:23:45', value: 1400, color: 'rgba(21, 129, 195, 1)' },
    { name: '08:00:27:12:34:56', value: 500, color: 'rgba(37, 172, 255, 1)' },
];

function TotalLengthOfPacketsHistogram() {
    // Find the maximum value in the data to set the x-scale domain
    const maxValue = Math.max(...data.map((entry) => entry.value));
    
    return (
            <div style={{
                position: 'relative',
                top: 5,
                left: 0,
                width: '140%',
                height: '34%',
                backgroundColor: 'white',
                borderRadius: '20px',
                padding: '20px',
                boxSizing: 'border-box',
                zIndex: -1,
                boxShadow: '4px 4px 8px rgba(0, 0, 0, 0.1)',
            }}>
                {/* Container for label and chart */}
                <div style={{ textAlign: 'center', marginBottom: '10px' }}>
                    {/* Label at the top */}
                    <div style={{
                        fontSize: '16px',
                        fontWeight: 'bold',
                        color: '#333',
                    }}>
                        Total Length Of Packets (bytes)
                    </div>
                </div>

                {/* Bar Chart */}
                <div style={{ position: 'relative', display: 'flex' }}>
                    <BarChart width={300} height={200} data={data}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis 
                        tick={false} // Hide tick labels
                        />
                        <YAxis />
                        <Tooltip />
                        <Bar dataKey="value">
                            {data.map((entry, index) => (
                                <Cell
                                    key={`cell-${index}`}
                                    fill={entry.color} // Apply the color for each bar
                                    stroke={entry.color}
                                />
                            ))}
                            <LabelList
                                dataKey="value"
                                position="bottom" // Position values on the top of the bars
                                style={{ fill: '#334' }} // Style for the labels
                            />
                        </Bar>
                    </BarChart>

                    {/* Legend positioned to the right */}
                    <Legend
                        layout="vertical"
                        align="right"
                        verticalAlign="" // Adjusted to "middle"
                        payload={
                            data.map((entry) => ({
                                value: entry.name,
                                type: "square",
                                color: entry.color,
                            }))
                        }
                    />
                </div>
            </div>
    );
}

export default TotalLengthOfPacketsHistogram;
