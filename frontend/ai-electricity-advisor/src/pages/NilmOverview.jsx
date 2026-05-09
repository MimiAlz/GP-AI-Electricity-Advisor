import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert, Button, Card, Col, DatePicker, Empty, Row, Select, Space, Spin, Statistic, Table, Tag, Tooltip, Typography,
} from 'antd';
import { BarChartOutlined, CalendarOutlined, CheckCircleOutlined, ThunderboltOutlined } from '@ant-design/icons';
import plotlyFactoryModule from 'react-plotly.js/factory.js';
import Plotly from 'plotly.js-dist-min';
import dayjs from 'dayjs';
import { houseApi, nilmApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';

const createPlotlyComponent =
  plotlyFactoryModule?.default?.default
  || plotlyFactoryModule?.default
  || plotlyFactoryModule;
const Plot = createPlotlyComponent(Plotly);
const { Title, Text, Paragraph } = Typography;

// Colour palette for appliances (up to 6)
const APPLIANCE_COLORS = ['#5b5ef4', '#f4845f', '#52c41a', '#faad14', '#13c2c2', '#eb2f96'];

/**
 * Adapt the raw API response into the internal dataset format used by the charts.
 *
 * API shape:
 *   { month, appliances[{name,total_kwh,on_minutes,peak_watts,daily_kwh,hourly_kwh}], ranking, total_mains_kwh }
 *
 * Internal dataset shape (mirrors what buildNilmDataset used to produce):
 *   { ranking, dailySeries, aggregateDaily, hourlyAverages, totalUsage, peakDay, monthLabel }
 */
function adaptApiResponse(apiData, monthValue) {
  const year  = monthValue.year();
  const mon   = monthValue.month(); // 0-based
  const nDays = monthValue.daysInMonth();
  const days  = Array.from({ length: nDays }, (_, i) =>
    dayjs(new Date(year, mon, i + 1)).format('MMM D'),
  );

  const total = apiData.total_mains_kwh || 1;

  const ranking = apiData.appliances.map((app, idx) => ({
    id:       app.name,
    labelKey: null,            // use name directly for real data
    color:    APPLIANCE_COLORS[idx % APPLIANCE_COLORS.length],
    total:    app.total_kwh,
    share:    total > 0 ? Math.round((app.total_kwh / total) * 100) : 0,
  }));

  const dailySeries = {};
  apiData.appliances.forEach((app) => {
    dailySeries[app.name] = app.daily_kwh.map((v, i) => ({ day: days[i] ?? `Day ${i + 1}`, value: v }));
  });

  // Aggregate across all appliances per day
  const aggValues = new Array(nDays).fill(0);
  apiData.appliances.forEach((app) => {
    app.daily_kwh.forEach((v, i) => { aggValues[i] += v; });
  });
  const aggregateDaily = aggValues.map((v, i) => ({ day: days[i] ?? `Day ${i + 1}`, value: v }));

  // Hourly averages keyed by appliance name
  const hourlyAverages = {};
  apiData.appliances.forEach((app) => {
    hourlyAverages[app.name] = app.hourly_kwh;
  });

  // Peak day (max of aggregate)
  const peakIdx = aggValues.indexOf(Math.max(...aggValues));
  const peakDay = { day: days[peakIdx], value: aggValues[peakIdx] };

  const monthLabel = monthValue.format('MMMM YYYY');

  return { ranking, dailySeries, aggregateDaily, hourlyAverages, totalUsage: total, peakDay, monthLabel };
}

export default function NilmOverview() {
  const { user } = useAuth();
  const { T, isRtl } = useLang();

  const [houses, setHouses] = useState([]);
  const [houseId, setHouseId] = useState(null);
  const [loadingHouses, setLoadingHouses] = useState(true);
  const [monthValue, setMonthValue] = useState(dayjs().startOf('month'));
  const [selectedApplianceId, setSelectedApplianceId] = useState(null);

  const [dataset, setDataset]               = useState(null);
  const [loading, setLoading]               = useState(false);
  const [apiError, setApiError]             = useState(null);
  const [availableMonths, setAvailableMonths] = useState([]);   // ["YYYY-MM", ...]
  const [loadingMonths, setLoadingMonths]   = useState(false);

  useEffect(() => {
    houseApi.list(user.national_id)
      .then((data) => {
        const list = Array.isArray(data) ? data : [];
        setHouses(list);
        if (list.length > 0) {
          setHouseId((currentHouseId) => currentHouseId || list[0].house_id);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingHouses(false));
  }, [user.national_id]);

  // Fetch available months whenever the selected house changes
  useEffect(() => {
    if (!houseId) {
      setAvailableMonths([]);
      return;
    }
    setLoadingMonths(true);
    setAvailableMonths([]);
    nilmApi.availableMonths(user.national_id, houseId)
      .then((data) => setAvailableMonths(data.available_months || []))
      .catch(() => setAvailableMonths([]))
      .finally(() => setLoadingMonths(false));
  }, [houseId, user.national_id]);

  const runDisaggregation = useCallback(async () => {
    if (!houseId || !monthValue) return;
    setLoading(true);
    setApiError(null);
    setDataset(null);
    try {
      const month = monthValue.format('YYYY-MM');
      const apiData = await nilmApi.disaggregate(user.national_id, houseId, month);
      setDataset(adaptApiResponse(apiData, monthValue));
    } catch (err) {
      setApiError(err.message || 'Disaggregation failed');
    } finally {
      setLoading(false);
    }
  }, [houseId, monthValue, user.national_id]);

  const houseOptions = houses.map((house) => ({ value: house.house_id, label: house.house_id }));

  useEffect(() => {
    if (dataset?.ranking?.length) {
      setSelectedApplianceId(dataset.ranking[0].id);
    } else {
      setSelectedApplianceId(null);
    }
  }, [dataset]);

  // Helper: resolve appliance display name (real API uses name directly; mock used labelKey)
  const appName = (item) => (item.labelKey ? (T[item.labelKey] || item.id) : item.id);

  const totalUsageTrace = useMemo(() => {
    if (!dataset) return [];
    return [{
      type: 'scatter',
      mode: 'lines+markers',
      name: T.totalConsumption,
      x: dataset.aggregateDaily.map((entry) => entry.day),
      y: dataset.aggregateDaily.map((entry) => entry.value),
      line: { color: '#1677ff', width: 3, shape: 'spline' },
      marker: { color: '#1677ff', size: 7 },
      hovertemplate: `%{x}<br>${T.totalConsumption}: %{y:.2f} kWh<extra></extra>`,
    }];
  }, [dataset, T.totalConsumption]);

  const applianceDisaggregationCharts = useMemo(() => {
    if (!dataset) return [];
    return dataset.ranking.map((item) => ({
      ...item,
      trace: [{
        type: 'scatter',
        mode: 'lines+markers',
        name: appName(item),
        x: dataset.dailySeries[item.id].map((entry) => entry.day),
        y: dataset.dailySeries[item.id].map((entry) => entry.value),
        line: { color: item.color, width: 2.5, shape: 'spline' },
        marker: { color: item.color, size: 6 },
        fill: 'tozeroy',
        fillcolor: `${item.color}18`,
        hovertemplate: `%{x}<br>${appName(item)}: %{y:.2f} kWh<extra></extra>`,
      }],
    }));
  }, [dataset, appName]);

  const shareTrace = useMemo(() => {
    if (!dataset) return [];
    return [{
      type: 'pie',
      hole: 0.58,
      sort: false,
      direction: 'clockwise',
      labels: dataset.ranking.map(appName),
      values: dataset.ranking.map((item) => item.total),
      marker: { colors: dataset.ranking.map((item) => item.color) },
      textinfo: 'label+percent',
      hovertemplate: '%{label}<br>%{value:.2f} kWh (%{percent})<extra></extra>',
    }];
  }, [dataset, appName]);

  const selectedAppliance = useMemo(() => {
    if (!dataset || !selectedApplianceId) return null;
    return dataset.ranking.find((item) => item.id === selectedApplianceId) || null;
  }, [dataset, selectedApplianceId]);

  const rankingTrace = useMemo(() => {
    if (!dataset) return [];
    return [{
      type: 'bar',
      orientation: 'h',
      y: [...dataset.ranking].reverse().map(appName),
      x: [...dataset.ranking].reverse().map((item) => item.total),
      marker: { color: [...dataset.ranking].reverse().map((item) => item.color) },
      text: [...dataset.ranking].reverse().map((item) => `${item.total.toFixed(1)} kWh`),
      textposition: 'outside',
      hovertemplate: '%{y}<br>%{x:.2f} kWh<extra></extra>',
    }];
  }, [dataset, appName]);

  const hourlyTrace = useMemo(() => {
    if (!dataset || !selectedAppliance) return [];
    return [{
      type: 'scatter',
      mode: 'lines+markers',
      x: Array.from({ length: 24 }, (_, hour) => `${hour}:00`),
      y: dataset.hourlyAverages[selectedAppliance.id],
      line: { color: selectedAppliance.color, width: 3, shape: 'spline' },
      marker: { size: 7, color: selectedAppliance.color },
      fill: 'tozeroy',
      fillcolor: `${selectedAppliance.color}22`,
      hovertemplate: '%{x}<br>%{y:.3f} kWh<extra></extra>',
      name: appName(selectedAppliance),
    }];
  }, [dataset, selectedAppliance, appName]);

  const tableData = useMemo(() => {
    if (!dataset) return [];
    return dataset.ranking.map((item, index) => ({
      key: item.id,
      rank: index + 1,
      appliance: appName(item),
      total: item.total.toFixed(1),
      share: `${item.share}%`,
      peakHour: `${dataset.hourlyAverages[item.id].indexOf(Math.max(...dataset.hourlyAverages[item.id]))}:00`,
      color: item.color,
    }));
  }, [dataset, appName]);

  const columns = [
    { title: '#', dataIndex: 'rank', key: 'rank', width: 70 },
    {
      title: T.applianceRanking,
      dataIndex: 'appliance',
      key: 'appliance',
      render: (value, record) => (
        <Space>
          <span style={{ width: 10, height: 10, borderRadius: 999, background: record.color, display: 'inline-block' }} />
          <span>{value}</span>
        </Space>
      ),
    },
    { title: T.totalConsumption, dataIndex: 'total', key: 'total', render: (value) => `${value} kWh` },
    { title: T.shareOfMonth, dataIndex: 'share', key: 'share' },
    { title: T.hourlySignature, dataIndex: 'peakHour', key: 'peakHour' },
  ];

  const topAppliance = dataset?.ranking?.[0];

  return (
    <div style={{ direction: isRtl ? 'rtl' : 'ltr' }}>
      <Card style={{ borderRadius: 12, marginBottom: 16 }}>
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          <Space>
            <ThunderboltOutlined />
            <Title level={4} style={{ margin: 0 }}>{T.nilmOverviewTitle}</Title>
          </Space>
          <Paragraph type="secondary" style={{ margin: 0 }}>{T.nilmOverviewSubtitle}</Paragraph>
        </Space>

        <Row gutter={[16, 12]} align="bottom" style={{ marginTop: 20, marginBottom: 20 }}>
          <Col xs={24} md={10}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">{T.selectHouse}</Text>
              <Select
                loading={loadingHouses}
                options={houseOptions}
                value={houseId}
                onChange={setHouseId}
                placeholder={T.selectHouse}
                style={{ width: '100%' }}
              />
            </Space>
          </Col>
          <Col xs={24} md={8}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">{T.nilmMonth}</Text>
              <DatePicker
                picker="month"
                value={monthValue}
                onChange={setMonthValue}
                style={{ width: '100%' }}
              />
            </Space>
          </Col>
          <Col xs={24} md={6}>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              onClick={runDisaggregation}
              loading={loading}
              disabled={!houseId || !monthValue || loadingHouses || !availableMonths.includes(monthValue?.format('YYYY-MM'))}
              style={{ width: '100%', height: 40, marginTop: 22 }}
            >
              {T.nilmRun || 'Run NILM'}
            </Button>
          </Col>
        </Row>

        {/* ── Data availability panel ─────────────────────────────────────── */}
        {houseId && (
          <Card
            size="small"
            style={{ borderRadius: 10, marginBottom: 16, background: '#f8f9ff', border: '1px solid #e8eaff' }}
            title={
              <Space>
                <CalendarOutlined style={{ color: '#5b5ef4' }} />
                <span style={{ fontSize: 13, fontWeight: 600 }}>{T.nilmAvailableMonths || 'Available Months'}</span>
              </Space>
            }
          >
            {loadingMonths ? (
              <Spin size="small" />
            ) : availableMonths.length === 0 ? (
              <Tag color="warning">{T.nilmNoData || 'No meter readings found for this house'}</Tag>
            ) : (
              <Space wrap>
                {availableMonths.map((m) => {
                  const isSelected = monthValue?.format('YYYY-MM') === m;
                  return (
                    <Tooltip key={m} title={T.nilmClickToSelect || 'Click to select this month'}>
                      <Tag
                        icon={isSelected ? <CheckCircleOutlined /> : null}
                        color={isSelected ? 'blue' : 'default'}
                        style={{ cursor: 'pointer', userSelect: 'none', fontSize: 13, padding: '3px 10px' }}
                        onClick={() => setMonthValue(dayjs(m, 'YYYY-MM'))}
                      >
                        {dayjs(m, 'YYYY-MM').format('MMM YYYY')}
                      </Tag>
                    </Tooltip>
                  );
                })}
                <Tag color="green" style={{ fontSize: 12 }}>
                  {availableMonths.length} {T.nilmMonthsAvailable || 'month(s) with data'}
                </Tag>
              </Space>
            )}
          </Card>
        )}

        {loading && (
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: 16, color: '#999' }}>{T.nilmProcessing || 'Running disaggregation\u2026'}</div>
          </div>
        )}

        {!loading && apiError && (
          <Alert type="error" showIcon message={apiError} style={{ marginBottom: 16 }} />
        )}

        {!loading && dataset && (
          <>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col xs={24} sm={8}>
                <Card size="small" style={{ borderRadius: 8, background: '#f6f8ff' }}>
                  <Statistic title={T.totalConsumption} value={dataset.totalUsage} precision={1} suffix="kWh" valueStyle={{ color: '#1677ff' }} />
                </Card>
              </Col>
              <Col xs={24} sm={8}>
                <Card size="small" style={{ borderRadius: 8, background: '#fff7f0' }}>
                  <Statistic title={T.topAppliance} value={topAppliance ? appName(topAppliance) : '--'} valueStyle={{ color: '#fa8c16', fontSize: 18 }} />
                </Card>
              </Col>
              <Col xs={24} sm={8}>
                <Card size="small" style={{ borderRadius: 8, background: '#f6ffed' }}>
                  <Statistic title={T.busiestDay} value={dataset.peakDay ? `${dataset.peakDay.day} • ${dataset.peakDay.value.toFixed(1)} kWh` : '--'} valueStyle={{ color: '#52c41a', fontSize: 18 }} />
                </Card>
              </Col>
            </Row>

            <Row gutter={[16, 16]}>
              <Col xs={24} xl={15}>
                <Card title={T.monthlyDisaggregation} style={{ borderRadius: 12, height: '100%' }}>
                  <Plot
                    data={totalUsageTrace}
                    layout={{
                      autosize: true,
                      margin: { t: 20, r: 20, b: 50, l: 55 },
                      legend: { orientation: 'h', y: -0.22, x: 0.5, xanchor: 'center' },
                      xaxis: { title: T.month, showgrid: false },
                      yaxis: { title: 'kWh', gridcolor: '#f0f0f0' },
                      plot_bgcolor: '#fcfcff',
                      paper_bgcolor: '#fcfcff',
                      hovermode: 'x unified',
                    }}
                    config={{ displayModeBar: true, responsive: true }}
                    style={{ width: '100%', height: 420 }}
                    useResizeHandler
                  />
                </Card>
              </Col>
              <Col xs={24} xl={9}>
                <Card title={T.applianceShare} style={{ borderRadius: 12, height: '100%' }}>
                  <Plot
                    data={shareTrace}
                    layout={{
                      autosize: true,
                      margin: { t: 10, r: 10, b: 10, l: 10 },
                      paper_bgcolor: '#fcfcff',
                      plot_bgcolor: '#fcfcff',
                      showlegend: false,
                      annotations: [{
                        text: `<b>${dataset.totalUsage.toFixed(1)} kWh</b><br>${dataset.monthLabel}`,
                        showarrow: false,
                        font: { size: 14, color: '#302b63' },
                      }],
                    }}
                    config={{ displayModeBar: false, responsive: true }}
                    style={{ width: '100%', height: 320 }}
                    useResizeHandler
                  />

                  <Space direction="vertical" size={8} style={{ width: '100%' }}>
                    {dataset.ranking.map((item, index) => (
                      <Card key={item.id} size="small" style={{ borderRadius: 10, background: index === 0 ? '#f7f8ff' : '#fff' }}>
                        <Row align="middle" justify="space-between" gutter={12}>
                          <Col>
                            <Space>
                              <span style={{ width: 10, height: 10, borderRadius: 999, background: item.color, display: 'inline-block' }} />
                              <Text strong>{appName(item)}</Text>
                            </Space>
                          </Col>
                          <Col>
                            <Space size={10}>
                              <Tag color="blue">{item.total.toFixed(1)} kWh</Tag>
                              <Tag>{item.share}%</Tag>
                            </Space>
                          </Col>
                        </Row>
                      </Card>
                    ))}
                  </Space>
                </Card>
              </Col>
            </Row>

            <div style={{ marginTop: 14, textAlign: 'center' }}>
              <Tag color="green">{T.nilmLiveData || 'Results from live NILM model'}</Tag>
            </div>

            <Card style={{ borderRadius: 12, marginTop: 16 }}>
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Title level={4} style={{ margin: 0 }}>{T.monthlyDisaggregation}</Title>
                <Paragraph type="secondary" style={{ margin: 0 }}>
                  {T.descendingOrder}
                </Paragraph>
              </Space>

              <Row gutter={[16, 16]} style={{ marginTop: 4 }}>
                {applianceDisaggregationCharts.map((item) => (
                  <Col xs={24} lg={12} key={item.id}>
                    <Card
                      title={
                        <Space>
                          <span style={{ width: 10, height: 10, borderRadius: 999, background: item.color, display: 'inline-block' }} />
                          <span>{appName(item)}</span>
                        </Space>
                      }
                      extra={<Tag color="blue">{item.total.toFixed(1)} kWh</Tag>}
                      style={{ borderRadius: 12, height: '100%' }}
                    >
                      <Plot
                        data={item.trace}
                        layout={{
                          autosize: true,
                          margin: { t: 12, r: 16, b: 45, l: 50 },
                          xaxis: { title: T.month, showgrid: false },
                          yaxis: { title: 'kWh', gridcolor: '#f0f0f0' },
                          plot_bgcolor: '#fcfcff',
                          paper_bgcolor: '#fcfcff',
                          hovermode: 'x unified',
                          showlegend: false,
                        }}
                        config={{ displayModeBar: false, responsive: true }}
                        style={{ width: '100%', height: 260 }}
                        useResizeHandler
                      />
                    </Card>
                  </Col>
                ))}
              </Row>
            </Card>

            <Card style={{ borderRadius: 12, marginTop: 16 }}>
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Space>
                  <BarChartOutlined />
                  <Title level={4} style={{ margin: 0 }}>{T.nilmRankingTitle}</Title>
                </Space>
                <Paragraph type="secondary" style={{ margin: 0 }}>{T.nilmRankingSubtitle}</Paragraph>
              </Space>

              <Row gutter={[16, 12]} align="bottom" style={{ marginTop: 20, marginBottom: 20 }}>
                <Col xs={24} md={8}>
                  <Card size="small" style={{ borderRadius: 8, background: '#fff7f0' }}>
                    <Statistic title={T.descendingOrder} value={dataset.ranking.length} suffix={T.activeAppliances} valueStyle={{ color: '#fa8c16' }} />
                  </Card>
                </Col>
                <Col xs={24} md={8}>
                  <Card size="small" style={{ borderRadius: 8, background: '#f6f8ff' }}>
                    <Statistic title={T.topAppliance} value={topAppliance ? appName(topAppliance) : '--'} valueStyle={{ color: '#1677ff', fontSize: 18 }} />
                  </Card>
                </Col>
                <Col xs={24} md={8}>
                  <Space direction="vertical" style={{ width: '100%' }}>
                    <Text type="secondary">{T.topAppliance}</Text>
                    <Select
                      value={selectedApplianceId}
                      onChange={setSelectedApplianceId}
                      options={dataset.ranking.map((item) => ({ value: item.id, label: appName(item) }))}
                      placeholder={T.topAppliance}
                      style={{ width: '100%' }}
                    />
                  </Space>
                </Col>
              </Row>

              <Row gutter={[16, 16]}>
                <Col xs={24} xl={13}>
                  <Card title={T.applianceRanking} style={{ borderRadius: 12, height: '100%' }}>
                    <Plot
                      data={rankingTrace}
                      layout={{
                        autosize: true,
                        margin: { t: 10, r: 30, b: 40, l: 110 },
                        xaxis: { title: 'kWh', gridcolor: '#f0f0f0' },
                        yaxis: { automargin: true },
                        plot_bgcolor: '#fcfcff',
                        paper_bgcolor: '#fcfcff',
                      }}
                      config={{ displayModeBar: false, responsive: true }}
                      style={{ width: '100%', height: 360 }}
                      useResizeHandler
                    />
                  </Card>
                </Col>
                <Col xs={24} xl={11}>
                  <Card title={T.hourlySignature} extra={selectedAppliance ? <Tag color="blue">{appName(selectedAppliance)}</Tag> : null} style={{ borderRadius: 12, height: '100%' }}>
                    <Plot
                      data={hourlyTrace}
                      layout={{
                        autosize: true,
                        margin: { t: 10, r: 20, b: 45, l: 55 },
                        xaxis: { title: T.time, showgrid: false },
                        yaxis: { title: `${T.avgHourlyLoad} (kWh)`, gridcolor: '#f0f0f0' },
                        plot_bgcolor: '#fcfcff',
                        paper_bgcolor: '#fcfcff',
                        hovermode: 'x unified',
                      }}
                      config={{ displayModeBar: false, responsive: true }}
                      style={{ width: '100%', height: 360 }}
                      useResizeHandler
                    />
                  </Card>
                </Col>
              </Row>

              <Card title={T.descendingOrder} style={{ borderRadius: 12, marginTop: 16 }}>
                <Table
                  columns={columns}
                  dataSource={tableData}
                  pagination={false}
                  size="middle"
                  scroll={{ x: 640 }}
                />
              </Card>
            </Card>
          </>
        )}

        {!loading && !dataset && !apiError && (
          <Empty description={T.selectMonthPrompt || 'Select a house and month, then click Run NILM'} />
        )}
      </Card>
    </div>
  );
}