import { useState, useEffect, useMemo } from 'react';
import {
  Card, Select, DatePicker, Typography, Space, Row, Col, Statistic, Tag, Empty, Segmented,
} from 'antd';
import { ThunderboltOutlined } from '@ant-design/icons';
import plotlyFactoryModule from 'react-plotly.js/factory.js';
import Plotly from 'plotly.js-dist-min';
import dayjs from 'dayjs';
import { houseApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';

const createPlotlyComponent =
  plotlyFactoryModule?.default?.default
  || plotlyFactoryModule?.default
  || plotlyFactoryModule;
const Plot = createPlotlyComponent(Plotly);
const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

// Mock disaggregation data generator
function generateMockData(startDate, days = 7) {
  const appliances = ['kettle', 'fridge', 'washer', 'dishwasher', 'microwave', 'tv'];
  const colors = ['#1677ff', '#52c41a', '#fa8c16', '#eb2f96', '#722ed1', '#13c2c2'];
  const baseloads = { kettle: 0.03, fridge: 0.15, washer: 0.08, dishwasher: 0.06, microwave: 0.04, tv: 0.07 };

  const timestamps = [];
  const data = {};
  appliances.forEach((a) => { data[a] = []; });
  data['aggregate'] = [];

  for (let d = 0; d < days; d++) {
    for (let h = 0; h < 24; h++) {
      const ts = dayjs(startDate).add(d, 'day').add(h, 'hour').toISOString();
      timestamps.push(ts);
      let agg = 0;
      appliances.forEach((a) => {
        const spike = (h >= 7 && h <= 9) || (h >= 12 && h <= 13) || (h >= 18 && h <= 21)
          ? Math.random() * 1.5 : 0;
        const val = parseFloat((baseloads[a] + spike + Math.random() * 0.05).toFixed(3));
        data[a].push(val);
        agg += val;
      });
      data['aggregate'].push(parseFloat(agg.toFixed(3)));
    }
  }
  return { timestamps, appliances, data, colors };
}

export default function HouseDisaggregation() {
  const { user } = useAuth();
  const { T, isRtl } = useLang();

  const [houses, setHouses] = useState([]);
  const [houseId, setHouseId] = useState(null);
  const [loadingHouses, setLoadingHouses] = useState(true);
  const [dateRange, setDateRange] = useState([dayjs().subtract(7, 'day'), dayjs()]);
  const [viewMode, setViewMode] = useState('stacked');

  useEffect(() => {
    houseApi.list(user.national_id)
      .then((data) => {
        const list = Array.isArray(data) ? data : [];
        setHouses(list);
        if (list.length > 0) setHouseId(list[0].house_id);
      })
      .catch(() => {})
      .finally(() => setLoadingHouses(false));
  }, [user.national_id]);

  const mockData = useMemo(() => {
    if (!dateRange || !dateRange[0]) return null;
    const days = dateRange[1]
      ? Math.max(1, Math.min(dateRange[1].diff(dateRange[0], 'day'), 14))
      : 7;
    return generateMockData(dateRange[0].toDate(), days);
  }, [dateRange, houseId]);

  const traces = useMemo(() => {
    if (!mockData) return [];
    const { timestamps, appliances, data, colors } = mockData;

    const appTraces = appliances.map((a, i) => ({
      type: 'scatter',
      mode: 'lines',
      name: T[`appliance_${a}`] || a,
      x: timestamps,
      y: data[a],
      line: { color: colors[i], width: 1.5 },
      fill: viewMode === 'stacked' ? 'tonexty' : 'none',
      stackgroup: viewMode === 'stacked' ? 'one' : undefined,
    }));

    const aggTrace = {
      type: 'scatter',
      mode: 'lines',
      name: T.aggregate,
      x: timestamps,
      y: data['aggregate'],
      line: { color: '#f5222d', width: 2, dash: 'dot' },
    };

    return [...appTraces, aggTrace];
  }, [mockData, viewMode, T]);

  const totalKwh = useMemo(() => {
    if (!mockData) return 0;
    return mockData.data.aggregate.reduce((s, v) => s + v, 0).toFixed(1);
  }, [mockData]);

  const peakKw = useMemo(() => {
    if (!mockData) return 0;
    return Math.max(...mockData.data.aggregate).toFixed(2);
  }, [mockData]);

  const houseOptions = houses.map((h) => ({ value: h.house_id, label: h.house_id }));

  return (
    <div style={{ direction: isRtl ? 'rtl' : 'ltr' }}>
      <Card
        title={
          <Space>
            <ThunderboltOutlined />
            <Title level={4} style={{ margin: 0 }}>{T.navDisaggregation}</Title>
          </Space>
        }
        style={{ borderRadius: 12, marginBottom: 16 }}
      >
        {/* Controls */}
        <Row gutter={[16, 12]} align="middle" style={{ marginBottom: 16 }}>
          <Col xs={24} sm={8}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">{T.selectHouse}</Text>
              <Select
                loading={loadingHouses}
                options={houseOptions}
                value={houseId}
                onChange={setHouseId}
                style={{ width: '100%' }}
                placeholder={T.selectHouse}
              />
            </Space>
          </Col>
          <Col xs={24} sm={12}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">{T.dateRange}</Text>
              <RangePicker
                value={dateRange}
                onChange={setDateRange}
                style={{ width: '100%' }}
                disabledDate={(d) => d && d > dayjs()}
              />
            </Space>
          </Col>
          <Col xs={24} sm={4}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">{T.chartType}</Text>
              <Segmented
                options={[
                  { label: T.stacked, value: 'stacked' },
                  { label: T.lines, value: 'lines' },
                ]}
                value={viewMode}
                onChange={setViewMode}
              />
            </Space>
          </Col>
        </Row>

        {/* KPI row */}
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col span={12}>
            <Card size="small" style={{ borderRadius: 8, background: '#f6f8ff' }}>
              <Statistic
                title={T.totalConsumption}
                value={totalKwh}
                suffix="kWh"
                precision={1}
                valueStyle={{ color: '#1677ff' }}
              />
            </Card>
          </Col>
          <Col span={12}>
            <Card size="small" style={{ borderRadius: 8, background: '#fff7f0' }}>
              <Statistic
                title={T.peakPower}
                value={peakKw}
                suffix="kW"
                precision={2}
                valueStyle={{ color: '#fa8c16' }}
              />
            </Card>
          </Col>
        </Row>

        {/* Chart */}
        {houseId && mockData ? (
          <Plot
            data={traces}
            layout={{
              autosize: true,
              margin: { t: 20, r: 20, b: 60, l: 60 },
              legend: {
                orientation: 'h',
                y: -0.18,
                xanchor: 'center',
                x: 0.5,
              },
              xaxis: { title: T.time, showgrid: false },
              yaxis: { title: `${T.power} (kW)`, gridcolor: '#f0f0f0' },
              plot_bgcolor: '#fcfcff',
              paper_bgcolor: '#fcfcff',
              hovermode: 'x unified',
            }}
            config={{ displayModeBar: true, responsive: true }}
            style={{ width: '100%', height: 420 }}
            useResizeHandler
          />
        ) : (
          <Empty description={T.selectHousePrompt} />
        )}

        <div style={{ marginTop: 8, textAlign: 'center' }}>
          <Tag color="warning">{T.mockDataNote}</Tag>
        </div>
      </Card>
    </div>
  );
}
