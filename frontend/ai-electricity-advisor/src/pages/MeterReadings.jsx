import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Card, Select, Typography, Space, Row, Col, Table, Button,
  Upload, message, Statistic, Alert, Popconfirm, Tag, Progress,
  Tooltip, Empty,
} from 'antd';
import {
  DatabaseOutlined, UploadOutlined, DeleteOutlined, ReloadOutlined,
  CheckCircleOutlined, WarningOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { houseApi, meterApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';

const { Title, Text } = Typography;
const { Option } = Select;

const MIN_ROWS = 1776; // 37 days × 48 half-hour slots

// ---------------------------------------------------------------------------
// CSV parser — expects two columns: timestamp, kwh_reading (with or without header)
// ---------------------------------------------------------------------------
function parseCsv(text) {
  const lines = text.trim().split(/\r?\n/);
  const rows = [];
  const errors = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;

    const parts = line.split(',');
    if (parts.length < 2) {
      errors.push(`Line ${i + 1}: expected 2 columns, got ${parts.length}`);
      continue;
    }

    const tsRaw  = parts[0].trim().replace(/^"|"$/g, '');
    const kwhRaw = parts[1].trim().replace(/^"|"$/g, '');

    // Skip header row
    if (isNaN(Number(kwhRaw))) continue;

    const parsed = dayjs(tsRaw);
    if (!parsed.isValid()) {
      errors.push(`Line ${i + 1}: invalid timestamp "${tsRaw}"`);
      continue;
    }

    const kwh = parseFloat(kwhRaw);
    if (kwh < 0) {
      errors.push(`Line ${i + 1}: negative kWh value (${kwh})`);
      continue;
    }

    rows.push({ ts: parsed.toISOString(), kwh_reading: kwh });
  }

  return { rows, errors };
}

export default function MeterReadings() {
  const { user } = useAuth();
  const { T, isRtl } = useLang();

  const [houses, setHouses]             = useState([]);
  const [houseId, setHouseId]           = useState(null);
  const [loadingHouses, setLoadingHouses] = useState(true);

  const [summary, setSummary]           = useState(null); // { count, has_enough_data }
  const [loadingSummary, setLoadingSummary] = useState(false);

  const [recentRows, setRecentRows]     = useState([]);

  const [uploading, setUploading]       = useState(false);
  const [parseErrors, setParseErrors]   = useState([]);
  const [deleting, setDeleting]         = useState(false);

  const refreshTimerRef = useRef(null);

  // ── Load houses ────────────────────────────────────────────────────────────
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

  // ── Fetch summary + recent readings for selected house ────────────────────
  const fetchSummary = useCallback(async () => {
    if (!houseId) return;
    setLoadingSummary(true);
    try {
      const data = await meterApi.list(user.national_id, houseId, 96); // last 2 days for preview
      setSummary({
        count: data.count,
        has_enough_data: data.has_enough_data,
        min_rows_required: data.min_rows_required,
      });
      setRecentRows(data.readings || []);
    } catch {
      setSummary(null);
      setRecentRows([]);
    } finally {
      setLoadingSummary(false);
    }
  }, [houseId, user.national_id]);

  useEffect(() => {
    setSummary(null);
    setRecentRows([]);
    setParseErrors([]);
    fetchSummary();
    return () => clearTimeout(refreshTimerRef.current);
  }, [fetchSummary]);

  // ── CSV upload handler ─────────────────────────────────────────────────────
  const handleUpload = async (file) => {
    setParseErrors([]);
    const text = await file.text();
    const { rows, errors } = parseCsv(text);

    if (errors.length > 0) {
      setParseErrors(errors.slice(0, 10));
    }

    if (rows.length === 0) {
      message.error(T.meterUploadEmpty);
      return false;
    }

    setUploading(true);
    try {
      // Upload in batches of 500 to avoid request-size limits
      const BATCH = 500;
      for (let i = 0; i < rows.length; i += BATCH) {
        await meterApi.bulkUpsert(user.national_id, houseId, rows.slice(i, i + BATCH));
      }
      message.success(T.meterUploadSuccess.replace('{n}', rows.length));
      refreshTimerRef.current = setTimeout(fetchSummary, 600);
    } catch (err) {
      message.error(err.message || T.meterUploadFailed);
    } finally {
      setUploading(false);
    }
    return false; // prevent antd auto-upload
  };

  // ── Delete all handler ─────────────────────────────────────────────────────
  const handleDeleteAll = async () => {
    setDeleting(true);
    try {
      await meterApi.deleteAll(user.national_id, houseId);
      message.success(T.meterDeletedAll);
      fetchSummary();
    } catch (err) {
      message.error(err.message || T.meterDeleteFailed);
    } finally {
      setDeleting(false);
    }
  };

  // ── Derived ────────────────────────────────────────────────────────────────
  const pct = summary ? Math.min(100, Math.round((summary.count / MIN_ROWS) * 100)) : 0;
  const ready = summary?.has_enough_data ?? false;

  const tableColumns = [
    {
      title: T.timestamp,
      dataIndex: 'ts',
      key: 'ts',
      render: (v) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: T.kwhReading,
      dataIndex: 'kwh_reading',
      key: 'kwh_reading',
      render: (v) => `${Number(v).toFixed(3)} kWh`,
    },
  ];

  return (
    <div style={{ direction: isRtl ? 'rtl' : 'ltr' }}>
      <Card
        title={
          <Space>
            <DatabaseOutlined />
            <Title level={4} style={{ margin: 0 }}>{T.navMeterReadings}</Title>
          </Space>
        }
        style={{ borderRadius: 12, marginBottom: 16 }}
      >
        {/* House selector */}
        <Row gutter={[16, 12]} style={{ marginBottom: 20 }}>
          <Col xs={24} sm={10}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text type="secondary">{T.selectHouse}</Text>
              <Select
                loading={loadingHouses}
                value={houseId}
                onChange={(v) => setHouseId(v)}
                style={{ width: '100%' }}
                placeholder={T.selectHouse}
              >
                {houses.map((h) => (
                  <Option key={h.house_id} value={h.house_id}>{h.house_id}</Option>
                ))}
              </Select>
            </Space>
          </Col>
          <Col xs={24} sm={4} style={{ display: 'flex', alignItems: 'flex-end' }}>
            <Button icon={<ReloadOutlined />} onClick={fetchSummary} loading={loadingSummary}>
              {T.refresh}
            </Button>
          </Col>
        </Row>

        {!houseId && <Empty description={T.selectHousePrompt} />}

        {houseId && (
          <>
            {/* Readiness KPIs */}
            <Row gutter={16} style={{ marginBottom: 20 }}>
              <Col xs={24} sm={8}>
                <Card size="small" style={{ borderRadius: 8, background: '#f6f8ff' }}>
                  <Statistic
                    title={T.totalReadings}
                    value={summary?.count ?? '—'}
                    suffix={`/ ${MIN_ROWS} min`}
                    valueStyle={{ color: ready ? '#52c41a' : '#fa8c16' }}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={8}>
                <Card size="small" style={{ borderRadius: 8 }}>
                  <Text type="secondary">{T.dataReadiness}</Text>
                  <Progress
                    percent={pct}
                    status={ready ? 'success' : 'active'}
                    style={{ marginTop: 8 }}
                  />
                </Card>
              </Col>
              <Col xs={24} sm={8} style={{ display: 'flex', alignItems: 'center' }}>
                {ready ? (
                  <Tag icon={<CheckCircleOutlined />} color="success" style={{ fontSize: 14, padding: '4px 12px' }}>
                    {T.readyToForecast}
                  </Tag>
                ) : (
                  <Tag icon={<WarningOutlined />} color="warning" style={{ fontSize: 14, padding: '4px 12px' }}>
                    {T.notEnoughData}
                  </Tag>
                )}
              </Col>
            </Row>

            {/* Upload */}
            <Card size="small" style={{ borderRadius: 8, marginBottom: 16 }}>
              <Title level={5} style={{ marginBottom: 8 }}>{T.uploadReadings}</Title>
              <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
                {T.uploadHint}
              </Text>
              <Upload
                accept=".csv"
                showUploadList={false}
                beforeUpload={handleUpload}
                disabled={!houseId || uploading}
              >
                <Button icon={<UploadOutlined />} loading={uploading} type="primary">
                  {T.uploadCsv}
                </Button>
              </Upload>

              {parseErrors.length > 0 && (
                <Alert
                  type="warning"
                  style={{ marginTop: 12 }}
                  message={T.csvParseWarning}
                  description={
                    <ul style={{ margin: 0, paddingInlineStart: 20 }}>
                      {parseErrors.map((e, i) => <li key={i}>{e}</li>)}
                    </ul>
                  }
                  showIcon
                />
              )}
            </Card>

            {/* Recent readings preview */}
            <Card size="small" style={{ borderRadius: 8, marginBottom: 16 }}>
              <Title level={5} style={{ marginBottom: 8 }}>{T.recentReadings}</Title>
              <Table
                dataSource={recentRows}
                columns={tableColumns}
                rowKey="reading_id"
                size="small"
                pagination={{ pageSize: 10, size: 'small' }}
                loading={loadingSummary}
                locale={{ emptyText: T.noReadings }}
              />
            </Card>

            {/* Danger zone */}
            <Card
              size="small"
              style={{ borderRadius: 8, borderColor: '#ff4d4f' }}
            >
              <Title level={5} style={{ color: '#ff4d4f', marginBottom: 8 }}>{T.dangerZone}</Title>
              <Space>
                <Popconfirm
                  title={T.deleteAllConfirm}
                  description={T.deleteAllWarning}
                  onConfirm={handleDeleteAll}
                  okText={T.yes}
                  cancelText={T.cancel}
                  okButtonProps={{ danger: true }}
                >
                  <Button danger icon={<DeleteOutlined />} loading={deleting}>
                    {T.deleteAllReadings}
                  </Button>
                </Popconfirm>
              </Space>
            </Card>
          </>
        )}
      </Card>
    </div>
  );
}
