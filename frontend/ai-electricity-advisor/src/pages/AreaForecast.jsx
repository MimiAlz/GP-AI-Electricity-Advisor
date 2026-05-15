import { useEffect, useMemo, useState } from 'react';
import {
	Alert, Badge, Button, Card, Col, DatePicker, Row, Space, Statistic, Tag, Tooltip, Typography,
} from 'antd';
import {
	CalendarOutlined, CheckCircleOutlined, EnvironmentOutlined, SendOutlined,
} from '@ant-design/icons';
import plotlyFactoryModule from 'react-plotly.js/factory.js';
import Plotly from 'plotly.js-dist-min';
import dayjs from 'dayjs';
import { xgbForecastApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';

const createPlotlyComponent =
	plotlyFactoryModule?.default?.default
	|| plotlyFactoryModule?.default
	|| plotlyFactoryModule;
const Plot = createPlotlyComponent(Plotly);
const { Title, Text, Paragraph } = Typography;

export default function AreaForecast() {
	const { user } = useAuth();
	const { T, isRtl } = useLang();

	const [forecastMonth, setForecastMonth] = useState(null);
	const [forecasting, setForecasting] = useState(false);
	const [forecastResult, setForecastResult] = useState(null);
	const [forecastError, setForecastError] = useState('');
	const [availableMonths, setAvailableMonths] = useState([]);
	const [loadingMonths, setLoadingMonths] = useState(true);

	// Fetch available months for the area model on mount
	useEffect(() => {
		xgbForecastApi.availableMonths('area')
			.then((data) => {
				const months = data?.available_months ?? [];
				setAvailableMonths(months);
				if (months.length > 0) setForecastMonth(dayjs(months[0]));
			})
			.catch(() => {})
			.finally(() => setLoadingMonths(false));
	}, []);

	const runForecast = async () => {
		if (!forecastMonth) return;
		setForecasting(true);
		setForecastError('');
		try {
			const monthStr = forecastMonth.format('YYYY-MM');
			const result = await xgbForecastApi.predict(null, monthStr, 'area', user?.national_id);
			setForecastResult({
				month: monthStr,
				predicted_kwh: result?.predicted_kwh ?? 0,
				estimated_bill_jod: result?.estimated_bill_jod ?? 0,
				tariff_tier: result?.tariff_tier ?? null,
			});
		} catch (err) {
			setForecastError(err.message || 'Area forecast failed.');
		} finally {
			setForecasting(false);
		}
	};

	const selectedMonthStr = forecastMonth ? forecastMonth.format('YYYY-MM') : null;
	const monthInAvailable = selectedMonthStr && availableMonths.includes(selectedMonthStr);

	const chartTraces = useMemo(() => {
		if (!forecastResult) return [];
		return [{
			type: 'bar',
			name: T.forecast,
			x: [forecastResult.month],
			y: [forecastResult.predicted_kwh],
			marker: { color: '#302b63' },
			text: [`${forecastResult.predicted_kwh.toLocaleString()} kWh`],
			textposition: 'outside',
		}];
	}, [forecastResult, T]);

	return (
		<div style={{ direction: isRtl ? 'rtl' : 'ltr' }}>
			<Card
				title={
					<Space>
						<EnvironmentOutlined />
						<Title level={4} style={{ margin: 0 }}>{T.navAreaForecast}</Title>
					</Space>
				}
				style={{ borderRadius: 12, marginBottom: 16 }}
			>
				<Space direction="vertical" size={4} style={{ width: '100%', marginBottom: 20 }}>
					<Paragraph type="secondary" style={{ margin: 0 }}>
						{T.areaForecastPageSubtitle}
					</Paragraph>
				</Space>

				{/* Controls */}
				<Row gutter={[16, 12]} align="bottom" style={{ marginBottom: 16 }}>
					<Col xs={24} sm={10}>
						<Space direction="vertical" style={{ width: '100%' }}>
							<Text type="secondary">{T.forecastMonth}</Text>
							<DatePicker
								picker="month"
								value={forecastMonth}
								onChange={setForecastMonth}
								style={{ width: '100%' }}
							/>
						</Space>
					</Col>
					<Col xs={24} sm={14}>
						<Button
							type="primary"
							icon={<SendOutlined />}
							size="large"
							onClick={runForecast}
							loading={forecasting}
							disabled={!monthInAvailable}
							style={{ width: '100%' }}
						>
							{T.runForecast}
						</Button>
					</Col>
				</Row>

				{/* Available months panel */}
				<div style={{ marginBottom: 16 }}>
					<Space style={{ marginBottom: 6 }}>
						<CalendarOutlined style={{ color: '#302b63' }} />
						<Text type="secondary">{T.nilmAvailableMonths}</Text>
						{!loadingMonths && (
							<Badge count={availableMonths.length} size="small" style={{ backgroundColor: '#302b63' }} />
						)}
					</Space>
					<div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
						{loadingMonths && <Text type="secondary">Loading…</Text>}
						{!loadingMonths && availableMonths.length === 0 && (
							<Tag color="warning">{T.nilmNoData}</Tag>
						)}
						{availableMonths.map((m) => {
							const isSelected = m === selectedMonthStr;
							return (
								<Tooltip key={m} title={T.nilmClickToSelect}>
									<Tag
										color={isSelected ? 'blue' : 'default'}
										icon={isSelected ? <CheckCircleOutlined /> : null}
										style={{ cursor: 'pointer', fontSize: 13 }}
										onClick={() => setForecastMonth(dayjs(m))}
									>
										{m}
									</Tag>
								</Tooltip>
							);
						})}
					</div>
				</div>

				{forecastError && (
					<Alert type="error" message={forecastError} showIcon style={{ marginBottom: 16 }} />
				)}

				{/* KPI cards */}
				{forecastResult && (
					<Row gutter={16} style={{ marginBottom: 16 }}>
						<Col xs={24} sm={8}>
							<Card size="small" style={{ borderRadius: 8, background: '#f6f8ff' }}>
								<Statistic
									title={T.forecastMonth}
									value={forecastResult.month}
									valueStyle={{ fontSize: 16, color: '#302b63' }}
								/>
							</Card>
						</Col>
						<Col xs={24} sm={8}>
							<Card size="small" style={{ borderRadius: 8, background: '#fff7f0' }}>
								<Statistic
									title={T.totalConsumption}
									value={forecastResult.predicted_kwh}
									suffix="kWh"
									precision={1}
									valueStyle={{ color: '#fa8c16' }}
								/>
							</Card>
						</Col>
						<Col xs={24} sm={4}>
							<Card size="small" style={{ borderRadius: 8, background: '#f6ffed' }}>
								<Statistic
									title={T.estimatedBill}
									value={forecastResult.estimated_bill_jod}
									suffix="JOD"
									precision={3}
									valueStyle={{ color: '#52c41a' }}
								/>
							</Card>
						</Col>
						<Col xs={24} sm={4}>
							<Card size="small" style={{ borderRadius: 8, background: '#fff0f6' }}>
								<Statistic
									title={T.tariffTier}
									value={forecastResult.tariff_tier}
									valueStyle={{ fontSize: 14, color: '#eb2f96' }}
								/>
							</Card>
						</Col>
					</Row>
				)}

				{/* Chart */}
				<Card title={T.areaForecastTitle} style={{ borderRadius: 12 }}>
					{forecastResult ? (
						<Plot
							data={chartTraces}
							layout={{
								autosize: true,
								margin: { t: 30, r: 20, b: 60, l: 80 },
								xaxis: { title: T.month, showgrid: false },
								yaxis: { title: 'kWh', gridcolor: '#f0f0f0' },
								plot_bgcolor: '#fcfcff',
								paper_bgcolor: '#fcfcff',
								showlegend: false,
							}}
							config={{ displayModeBar: false, responsive: true }}
							style={{ width: '100%', height: 350 }}
							useResizeHandler
						/>
					) : (
						<div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
							<Text type="secondary">{T.selectMonthPrompt}</Text>
						</div>
					)}
				</Card>
			</Card>
		</div>
	);
}
