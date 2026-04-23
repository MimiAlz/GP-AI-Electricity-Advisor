import { useState, useEffect, useMemo } from 'react';
import {
  Card, Select, DatePicker, Typography, Space, Row, Col, Statistic,
  Tag, Empty, Alert, Button,
} from 'antd';
import {
  LineChartOutlined, SendOutlined,
} from '@ant-design/icons';
import plotlyFactoryModule from 'react-plotly.js/factory.js';
import Plotly from 'plotly.js-dist-min';
import dayjs from 'dayjs';
import { houseApi, forecastApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';

const createPlotlyComponent =
  plotlyFactoryModule?.default?.default
  || plotlyFactoryModule?.default
  || plotlyFactoryModule;
const Plot = createPlotlyComponent(Plotly);
const { Title, Text, Paragraph } = Typography;
const { Option } = Select;

// Mock forecast curve (shape only — scaled to match real total from backend)
function generateForecast(month) {
  const timestamps = [];
  const values = [];
  const lower = [];
  const upper = [];
  const start = month ? dayjs(month).startOf('month') : dayjs().startOf('month').add(1, 'month');
  const days = start.daysInMonth();

  for (let d = 0; d < days; d++) {
    for (let h = 0; h < 24; h++) {
      const ts = start.add(d, 'day').add(h, 'hour').toISOString();
      const base = 0.35;
      const daytime = h >= 7 && h <= 22 ? Math.random() * 0.9 : Math.random() * 0.25;
      const v = parseFloat((base + daytime).toFixed(3));
      timestamps.push(ts);
      values.push(v);
      lower.push(parseFloat((v * 0.85).toFixed(3)));
      upper.push(parseFloat((v * 1.15).toFixed(3)));
    }
  }
  return { timestamps, values, lower, upper };
}

export default function HouseForecast() {
  const { user } = useAuth();
  const { T, isRtl } = useLang();

  const [houses, setHouses] = useState([]);
  const [houseId, setHouseId] = useState(null);
  const [loadingHouses, setLoadingHouses] = useState(true);
  const [forecastMonth, setForecastMonth] = useState(dayjs().add(1, 'month'));
  const [forecasting, setForecasting] = useState(false);
  const [forecastResult, setForecastResult] = useState(null);
  const [forecastError, setForecastError] = useState('');

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

  const runForecast = async () => {
    if (!houseId) return;
    setForecasting(true);
    setForecastError('');
    try {
      const monthStr = forecastMonth.format('YYYY-MM');
      const result = await forecastApi.create(user.national_id, houseId, monthStr);

      // API now returns real predicted_energy_kwh, estimated_bill_jod, tariff_tier
      const f = result?.forecast ?? {};
      const realTotalKwh    = f.predicted_energy_kwh ?? 0;
      const realBill        = f.estimated_bill_jod   ?? (realTotalKwh * 0.12);
      const realTier        = f.tariff_tier           ?? null;

      // Scale a synthetic hourly curve to the real total (backend returns scalar only)
      const mock = generateForecast(forecastMonth.toDate());
      const mockTotal = mock.values.reduce((s, v) => s + v, 0);
      const scale = mockTotal > 0 ? realTotalKwh / mockTotal : 1;
      const scaledValues = mock.values.map((v) => parseFloat((v * scale).toFixed(3)));
      const scaledLower  = mock.lower.map((v)  => parseFloat((v * scale).toFixed(3)));
      const scaledUpper  = mock.upper.map((v)  => parseFloat((v * scale).toFixed(3)));

      setForecastResult({
        month:               monthStr,
        timestamps:          mock.timestamps,
        predicted_kwh:       scaledValues,
        lower:               scaledLower,
        upper:               scaledUpper,
        total_kwh:           realTotalKwh.toFixed(2),
        estimated_bill_jod:  Number(realBill).toFixed(3),
        tariff_tier:         realTier,
        forecast_id:         f.forecast_id,
      });
    } catch (err) {
      setForecastError(err.message || 'Forecast failed.');
    } finally {
      setForecasting(false);
    }
  };

  const chartTraces = useMemo(() => {
    const traces = [];

    if (forecastResult) {
      if (forecastResult.lower && forecastResult.upper) {
        traces.push({
          type: 'scatter',
          mode: 'lines',
          name: T.confidenceBand,
          x: [...forecastResult.timestamps, ...[...forecastResult.timestamps].reverse()],
          y: [...forecastResult.upper, ...[...forecastResult.lower].reverse()],
          fill: 'toself',
          fillcolor: 'rgba(250,173,20,0.15)',
          line: { color: 'transparent' },
          showlegend: true,
        });
      }
      traces.push({
        type: 'scatter',
        mode: 'lines',
        name: T.forecast,
        x: forecastResult.timestamps,
        y: forecastResult.predicted_kwh,
        line: { color: '#fa8c16', width: 2, dash: 'dash' },
      });
    }

    return traces;
  }, [forecastResult, T]);

  const houseOptions = houses.map((h) => ({ value: h.house_id, label: h.house_id }));

  return (
    <div style={{ direction: isRtl ? 'rtl' : 'ltr' }}>
      <Card
        title={
          <Space>
            <LineChartOutlined />
            <Title level={4} style={{ margin: 0 }}>{T.navForecast}</Title>
          </Space>
        }
        style={{ borderRadius: 12, marginBottom: 16 }}
      >
        {/* Controls */}
        <Row gutter={[16, 12]} align="bottom" style={{ marginBottom: 20 }}>
          <Col xs={24} sm={8}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">{T.selectHouse}</Text>
              <Select
                loading={loadingHouses}
                options={houseOptions}
                value={houseId}
                onChange={(v) => { setHouseId(v); setForecastResult(null); }}
                style={{ width: '100%' }}
                placeholder={T.selectHouse}
              />
            </Space>
          </Col>
          <Col xs={24} sm={8}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">{T.forecastMonth}</Text>
              <DatePicker
                picker="month"
                value={forecastMonth}
                onChange={setForecastMonth}
                style={{ width: '100%' }}
                disabledDate={(d) => d && d < dayjs().endOf('month')}
              />
            </Space>
          </Col>
          <Col xs={24} sm={8}>
            <Button
              type="primary"
              icon={<SendOutlined />}
              size="large"
              onClick={runForecast}
              loading={forecasting}
              disabled={!houseId}
              style={{ width: '100%' }}
            >
              {T.runForecast}
            </Button>
          </Col>
        </Row>

        {/* Forecast KPI cards */}
        {forecastResult && (
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col xs={12} sm={6}>
              <Card size="small" style={{ borderRadius: 8, background: '#f6f8ff' }}>
                <Statistic
                  title={T.forecastMonth}
                  value={forecastResult.month}
                  valueStyle={{ fontSize: 16, color: '#1677ff' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small" style={{ borderRadius: 8, background: '#fff7f0' }}>
                <Statistic
                  title={T.totalConsumption}
                  value={forecastResult.total_kwh}
                  suffix="kWh"
                  precision={1}
                  valueStyle={{ color: '#fa8c16' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card size="small" style={{ borderRadius: 8, background: '#f6ffed' }}>
                <Statistic
                  title={T.estimatedBill}
                  value={forecastResult.estimated_bill_jod}
                  suffix="JOD"
                  precision={2}
                  valueStyle={{ color: '#52c41a' }}
                />
              </Card>
            </Col>
            {forecastResult.note && (
              <Col xs={12} sm={6}>
                <Tag color="warning" style={{ marginTop: 8 }}>{forecastResult.note}</Tag>
              </Col>
            )}
            {forecastResult.tariff_tier && (
              <Col xs={12} sm={6}>
                <Card size="small" style={{ borderRadius: 8, background: '#fff0f6' }}>
                  <Statistic
                    title={T.tariffTier}
                    value={forecastResult.tariff_tier}
                    valueStyle={{ fontSize: 15, color: '#eb2f96' }}
                  />
                </Card>
              </Col>
            )}
          </Row>
        )}

        {forecastError && (
          <Alert
            type="error"
            message={forecastError}
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        {/* Chart */}
        {houseId ? (
          <Plot
            data={chartTraces}
            layout={{
              autosize: true,
              margin: { t: 20, r: 20, b: 60, l: 60 },
              legend: { orientation: 'h', y: -0.18, xanchor: 'center', x: 0.5 },
              xaxis: { title: T.time, showgrid: false },
              yaxis: { title: `${T.power} (kW)`, gridcolor: '#f0f0f0' },
              plot_bgcolor: '#fcfcff',
              paper_bgcolor: '#fcfcff',
              hovermode: 'x unified',
              shapes: forecastResult?.timestamps?.length ? [{
                type: 'line',
                x0: forecastResult.timestamps[0],
                x1: forecastResult.timestamps[0],
                y0: 0,
                y1: 1,
                yref: 'paper',
                line: { color: '#fa8c16', width: 1.5, dash: 'dot' },
              }] : [],
            }}
            config={{ displayModeBar: true, responsive: true }}
            style={{ width: '100%', height: 420 }}
            useResizeHandler
          />
        ) : (
          <Empty description={T.selectHousePrompt} />
        )}
      </Card>
    </div>
  );
}
