// import { useState, useMemo } from 'react';
// import {
//   Card, Select, Typography, Space, Row, Col, Statistic, Radio, Tag, Segmented,
// } from 'antd';
// import { AreaChartOutlined } from '@ant-design/icons';
// import Plot from 'react-plotly.js';
// import dayjs from 'dayjs';
// import { useLang } from '../contexts/LangContext';

// const { Title, Text } = Typography;

// const AREAS = ['Amman', 'Zarqa', 'Irbid', 'Aqaba', 'Salt', 'Karak'];
// const AREA_COLORS = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2'];

// function generateAreaData(area, months = 12) {
//   const baseMap = {
//     Amman: 4.2, Zarqa: 3.1, Irbid: 2.8, Aqaba: 2.0, Salt: 1.5, Karak: 1.2,
//   };
//   const base = baseMap[area] || 2;
//   const timestamps = [];
//   const historical = [];
//   const forecast = [];
//   const lower = [];
//   const upper = [];

//   for (let m = -months; m <= 3; m++) {
//     const ts = dayjs().startOf('month').add(m, 'month').toISOString();
//     timestamps.push(ts);
//     const seasonal = Math.sin((dayjs().month() + m) / 12 * 2 * Math.PI) * 0.4;
//     const noise = (Math.random() - 0.5) * 0.3;
//     const val = parseFloat((base + seasonal + noise).toFixed(2));

//     if (m < 0) {
//       historical.push(val);
//       forecast.push(null);
//       lower.push(null);
//       upper.push(null);
//     } else {
//       historical.push(null);
//       const fv = parseFloat((base + seasonal + (Math.random() - 0.5) * 0.2).toFixed(2));
//       forecast.push(fv);
//       lower.push(parseFloat((fv * 0.88).toFixed(2)));
//       upper.push(parseFloat((fv * 1.12).toFixed(2)));
//     }
//   }

//   return { timestamps, historical, forecast, lower, upper };
// }

// function generateComparison(months = 12) {
//   return AREAS.map((area, i) => {
//     const d = generateAreaData(area, months);
//     return {
//       area,
//       color: AREA_COLORS[i],
//       ...d,
//     };
//   });
// }

// export default function AreaForecast() {
//   const { T, isRtl } = useLang();
//   const [selectedAreas, setSelectedAreas] = useState(['Amman', 'Zarqa', 'Irbid']);
//   const [chartMode, setChartMode] = useState('line');
//   const [months, setMonths] = useState(12);

//   const comparisonData = useMemo(() => generateComparison(months), [months]);

//   const chartTraces = useMemo(() => {
//     const traces = [];

//     comparisonData
//       .filter((d) => selectedAreas.includes(d.area))
//       .forEach((d) => {
//         // Confidence band
//         const validFcast = d.forecast.filter((v) => v !== null);
//         if (validFcast.length > 0) {
//           const fTimestamps = d.timestamps.filter((_, i) => d.forecast[i] !== null);
//           traces.push({
//             type: 'scatter',
//             mode: 'lines',
//             name: `${d.area} (band)`,
//             x: [...fTimestamps, ...[...fTimestamps].reverse()],
//             y: [...d.upper.filter((v) => v), ...[...d.lower.filter((v) => v)].reverse()],
//             fill: 'toself',
//             fillcolor: d.color.replace(')', ', 0.12)').replace('rgb', 'rgba'),
//             line: { color: 'transparent' },
//             showlegend: false,
//             hoverinfo: 'skip',
//           });
//         }

//         // Historical line
//         traces.push({
//           type: chartMode === 'bar' ? 'bar' : 'scatter',
//           mode: 'lines',
//           name: `${d.area} — ${T.historical}`,
//           x: d.timestamps.filter((_, i) => d.historical[i] !== null),
//           y: d.historical.filter((v) => v !== null),
//           ...(chartMode === 'bar' ? {} : { line: { color: d.color, width: 2 } }),
//           marker: { color: d.color },
//         });

//         // Forecast dashed
//         traces.push({
//           type: chartMode === 'bar' ? 'bar' : 'scatter',
//           mode: 'lines',
//           name: `${d.area} — ${T.forecast}`,
//           x: d.timestamps.filter((_, i) => d.forecast[i] !== null),
//           y: d.forecast.filter((v) => v !== null),
//           ...(chartMode === 'bar' ? { marker: { color: d.color, opacity: 0.5 } } : {
//             line: { color: d.color, width: 2, dash: 'dash' },
//           }),
//         });
//       });

//     return traces;
//   }, [comparisonData, selectedAreas, chartMode, T]);

//   // KPI: total forecasted for next 3 months
//   const kpis = useMemo(() => {
//     const totals = {};
//     comparisonData.forEach((d) => {
//       totals[d.area] = d.forecast.filter((v) => v).reduce((s, v) => s + v, 0).toFixed(1);
//     });
//     return totals;
//   }, [comparisonData]);

//   return (
//     <div style={{ direction: isRtl ? 'rtl' : 'ltr' }}>
//       <Card
//         title={
//           <Space>
//             <AreaChartOutlined />
//             <Title level={4} style={{ margin: 0 }}>{T.navAreaForecast}</Title>
//           </Space>
//         }
//         style={{ borderRadius: 12, marginBottom: 16 }}
//       >
//         {/* Controls */}
//         <Row gutter={[16, 12]} align="middle" style={{ marginBottom: 16 }}>
//           <Col xs={24} sm={10}>
//             <Space direction="vertical" style={{ width: '100%' }}>
//               <Text type="secondary">{T.selectAreas}</Text>
//               <Select
//                 mode="multiple"
//                 options={AREAS.map((a) => ({ value: a, label: a }))}
//                 value={selectedAreas}
//                 onChange={setSelectedAreas}
//                 style={{ width: '100%' }}
//                 maxTagCount={4}
//               />
//             </Space>
//           </Col>
//           <Col xs={24} sm={8}>
//             <Space direction="vertical" style={{ width: '100%' }}>
//               <Text type="secondary">{T.historicalMonths}</Text>
//               <Radio.Group
//                 value={months}
//                 onChange={(e) => setMonths(e.target.value)}
//                 buttonStyle="solid"
//               >
//                 <Radio.Button value={6}>6M</Radio.Button>
//                 <Radio.Button value={12}>12M</Radio.Button>
//                 <Radio.Button value={24}>24M</Radio.Button>
//               </Radio.Group>
//             </Space>
//           </Col>
//           <Col xs={24} sm={6}>
//             <Space direction="vertical" style={{ width: '100%' }}>
//               <Text type="secondary">{T.chartType}</Text>
//               <Segmented
//                 options={[
//                   { label: T.lines, value: 'line' },
//                   { label: T.bars, value: 'bar' },
//                 ]}
//                 value={chartMode}
//                 onChange={setChartMode}
//               />
//             </Space>
//           </Col>
//         </Row>

//         {/* KPI row */}
//         <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
//           {selectedAreas.slice(0, 4).map((area, i) => (
//             <Col xs={12} sm={6} key={area}>
//               <Card
//                 size="small"
//                 style={{ borderRadius: 8, borderLeft: `4px solid ${AREA_COLORS[AREAS.indexOf(area)]}` }}
//               >
//                 <Statistic
//                   title={area}
//                   value={kpis[area]}
//                   suffix="GWh"
//                   precision={1}
//                   valueStyle={{ color: AREA_COLORS[AREAS.indexOf(area)], fontSize: 18 }}
//                 />
//               </Card>
//             </Col>
//           ))}
//         </Row>

//         {/* Main chart */}
//         <Plot
//           data={chartTraces}
//           layout={{
//             autosize: true,
//             margin: { t: 20, r: 20, b: 80, l: 60 },
//             legend: {
//               orientation: 'h',
//               y: -0.22,
//               xanchor: 'center',
//               x: 0.5,
//               traceorder: 'normal',
//             },
//             xaxis: { title: T.month, showgrid: false },
//             yaxis: { title: 'GWh', gridcolor: '#f0f0f0' },
//             plot_bgcolor: '#fcfcff',
//             paper_bgcolor: '#fcfcff',
//             hovermode: 'x unified',
//             barmode: 'group',
//             shapes: [{
//               type: 'line',
//               x0: dayjs().startOf('month').toISOString(),
//               x1: dayjs().startOf('month').toISOString(),
//               y0: 0,
//               y1: 1,
//               yref: 'paper',
//               line: { color: '#f5222d', width: 1.5, dash: 'dot' },
//             }],
//           }}
//           config={{ displayModeBar: true, responsive: true }}
//           style={{ width: '100%', height: 460 }}
//           useResizeHandler
//         />

//         <div style={{ marginTop: 8, textAlign: 'center' }}>
//           <Tag color="warning">{T.mockDataNote}</Tag>
//         </div>
//       </Card>
//     </div>
//   );
// }
