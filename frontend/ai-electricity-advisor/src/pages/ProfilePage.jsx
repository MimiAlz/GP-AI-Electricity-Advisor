import { useEffect, useMemo, useState } from 'react';
import {
  Card,
  Row,
  Col,
  Statistic,
  Typography,
  Space,
  Table,
  Tag,
  Empty,
  Button,
  Popconfirm,
  message,
  Alert,
  Spin,
} from 'antd';
import {
  UserOutlined,
  HomeOutlined,
  FileSearchOutlined,
  DeleteOutlined,
  DollarOutlined,
} from '@ant-design/icons';
import dayjs from 'dayjs';
import { authApi, forecastApi, houseApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';

const { Title, Text } = Typography;

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const { T, isRtl } = useLang();

  const [loading, setLoading] = useState(true);
  const [houses, setHouses] = useState([]);
  const [historyRows, setHistoryRows] = useState([]);
  const [error, setError] = useState('');
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    let mounted = true;

    async function loadProfileData() {
      setLoading(true);
      setError('');

      try {
        const houseList = await houseApi.list(user.national_id);

        const forecastResults = await Promise.all(
          houseList.map(async (h) => {
            try {
              const res = await forecastApi.list(user.national_id, h.house_id);
              const forecasts = Array.isArray(res?.forecasts) ? res.forecasts : [];
              return forecasts.map((f) => ({ ...f, house_id: h.house_id }));
            } catch {
              return [];
            }
          }),
        );

        const merged = forecastResults.flat();
        merged.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

        if (!mounted) return;
        setHouses(houseList);
        setHistoryRows(merged);
      } catch (err) {
        if (!mounted) return;
        setError(err.message || T.profileLoadFailed);
      } finally {
        if (mounted) setLoading(false);
      }
    }

    loadProfileData();
    return () => {
      mounted = false;
    };
  }, [T.profileLoadFailed, user.national_id]);

  const thisMonth = dayjs().format('YYYY-MM');

  const thisMonthTotalBill = useMemo(() => {
    const latestByHouse = new Map();
    for (const r of historyRows) {
      const fm = r?.forecast_result?.forecast_month;
      if (fm !== thisMonth) continue;
      if (!latestByHouse.has(r.house_id)) {
        latestByHouse.set(r.house_id, Number(r?.estimated_bill_jod || 0));
      }
    }
    return Array.from(latestByHouse.values()).reduce((sum, v) => sum + v, 0);
  }, [historyRows, thisMonth]);

  const latestTierPerHouse = useMemo(() => {
    const byHouse = new Map();

    for (const row of historyRows) {
      if (!row?.house_id || byHouse.has(row.house_id)) continue;
      byHouse.set(row.house_id, {
        house_id: row.house_id,
        tariff_tier: row.tariff_tier || T.notAvailable,
        forecast_month: row?.forecast_result?.forecast_month || '-',
        estimated_bill_jod: Number(row?.estimated_bill_jod || 0),
      });
    }

    return Array.from(byHouse.values());
  }, [historyRows, T.notAvailable]);

  const handleDeleteAccount = async () => {
    setDeleting(true);
    try {
      await authApi.deleteAccount(user.national_id);
      message.success(T.accountDeleted);
      logout();
    } catch (err) {
      message.error(err.message || T.accountDeleteFailed);
    } finally {
      setDeleting(false);
    }
  };

  const historyColumns = [
    {
      title: T.houseId,
      dataIndex: 'house_id',
      key: 'house_id',
    },
    {
      title: T.forecastMonth,
      key: 'forecast_month',
      render: (_, r) => r?.forecast_result?.forecast_month || '-',
    },
    {
      title: T.totalConsumption,
      dataIndex: 'predicted_energy_kwh',
      key: 'predicted_energy_kwh',
      render: (v) => `${Number(v || 0).toFixed(2)} kWh`,
    },
    {
      title: T.estimatedBill,
      dataIndex: 'estimated_bill_jod',
      key: 'estimated_bill_jod',
      render: (v) => `${Number(v || 0).toFixed(3)} JOD`,
    },
    {
      title: T.tariffTier,
      dataIndex: 'tariff_tier',
      key: 'tariff_tier',
      render: (v) => <Tag color="blue">{v || T.notAvailable}</Tag>,
    },
    {
      title: T.createdAt,
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
  ];

  const houseTierColumns = [
    { title: T.houseId, dataIndex: 'house_id', key: 'house_id' },
    {
      title: T.tariffTier,
      dataIndex: 'tariff_tier',
      key: 'tariff_tier',
      render: (v) => <Tag color="purple">{v}</Tag>,
    },
    {
      title: T.forecastMonth,
      dataIndex: 'forecast_month',
      key: 'forecast_month',
    },
    {
      title: T.estimatedBill,
      dataIndex: 'estimated_bill_jod',
      key: 'estimated_bill_jod',
      render: (v) => `${Number(v || 0).toFixed(3)} JOD`,
    },
  ];

  return (
    <div style={{ direction: isRtl ? 'rtl' : 'ltr' }}>
      <Card
        style={{ borderRadius: 12, marginBottom: 16 }}
        title={
          <Space>
            <UserOutlined />
            <Title level={4} style={{ margin: 0 }}>{T.navProfile}</Title>
          </Space>
        }
      >
        <Text type="secondary">{T.profileSubtitle}</Text>
      </Card>

      {error && (
        <Alert
          type="error"
          showIcon
          message={error}
          style={{ marginBottom: 16 }}
        />
      )}

      {loading ? (
        <Card style={{ borderRadius: 12 }}>
          <Spin />
        </Card>
      ) : (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col xs={24} sm={12}>
              <Card size="small" style={{ borderRadius: 8, background: '#f6f8ff' }}>
                <Statistic
                  title={T.numberOfHouses}
                  value={houses.length}
                  prefix={<HomeOutlined />}
                />
              </Card>
            </Col>
            {/* <Col xs={24} sm={8}>
              <Card size="small" style={{ borderRadius: 8, background: '#fff7f0' }}>
                <Statistic
                  title={T.thisMonthEstimatedBills}
                  value={thisMonthTotalBill}
                  precision={3}
                  suffix="JOD"
                  prefix={<DollarOutlined />}
                />
              </Card>
            </Col> */}
            <Col xs={24} sm={12}>
              <Card size="small" style={{ borderRadius: 8, background: '#f6ffed' }}>
                <Statistic
                  title={T.forecastHistoryCount}
                  value={historyRows.length}
                  prefix={<FileSearchOutlined />}
                />
              </Card>
            </Col>
          </Row>

          <Card
            title={T.tariffPerHouse}
            style={{ borderRadius: 12, marginBottom: 16 }}
          >
            {latestTierPerHouse.length === 0 ? (
              <Empty description={T.noForecastsYet} />
            ) : (
              <Table
                rowKey="house_id"
                columns={houseTierColumns}
                dataSource={latestTierPerHouse}
                pagination={false}
                size="small"
              />
            )}
          </Card>

          <Card
            title={T.forecastHistory}
            style={{ borderRadius: 12, marginBottom: 16 }}
          >
            <Table
              rowKey={(r) => r.forecast_id}
              columns={historyColumns}
              dataSource={historyRows}
              pagination={{ pageSize: 8, size: 'small' }}
              size="small"
              locale={{ emptyText: T.noForecastsYet }}
            />
          </Card>

          <Card
            title={T.dangerZone}
            style={{ borderRadius: 12, borderColor: '#ff4d4f' }}
          >
            <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
              {T.deleteAccountWarning}
            </Text>
            <Popconfirm
              title={T.deleteAccountConfirm}
              description={T.deleteAccountWarning}
              onConfirm={handleDeleteAccount}
              okText={T.deleteAccount}
              cancelText={T.cancel}
              okButtonProps={{ danger: true, loading: deleting }}
            >
              <Button danger icon={<DeleteOutlined />} loading={deleting}>
                {T.deleteAccount}
              </Button>
            </Popconfirm>
          </Card>
        </>
      )}
    </div>
  );
}
