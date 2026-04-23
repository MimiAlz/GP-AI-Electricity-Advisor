import { useState } from 'react';
import {
  Card, Button, Typography, Space, Alert, Tag, Descriptions, Spin,
} from 'antd';
import { ApiOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons';
import { healthApi } from '../api/client';
import { useLang } from '../contexts/LangContext';

const { Title, Text, Paragraph } = Typography;

export default function BackendTest() {
  const { T, isRtl } = useLang();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  const runTest = async () => {
    setLoading(true);
    setResult(null);
    setError('');
    const start = Date.now();
    try {
      const text = await healthApi.hello();
      const elapsed = Date.now() - start;
      setResult({ text, elapsed });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ direction: isRtl ? 'rtl' : 'ltr', maxWidth: 600, margin: '0 auto' }}>
      <Card
        title={
          <Space>
            <ApiOutlined />
            <Title level={4} style={{ margin: 0 }}>{T.navBackendTest}</Title>
          </Space>
        }
        style={{ borderRadius: 12 }}
      >
        <Paragraph type="secondary" style={{ marginBottom: 20 }}>
          {T.backendTestDesc}
        </Paragraph>

        <Button
          type="primary"
          icon={<ApiOutlined />}
          onClick={runTest}
          loading={loading}
          size="large"
          style={{ marginBottom: 20 }}
        >
          {T.testBackend}
        </Button>

        {error && (
          <Alert
            type="error"
            icon={<CloseCircleOutlined />}
            message={T.connectionFailed}
            description={error}
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        {result && (
          <Alert
            type="success"
            icon={<CheckCircleOutlined />}
            message={T.connectionOk}
            description={
              <Descriptions column={1} size="small" style={{ marginTop: 8 }}>
                <Descriptions.Item label={T.response}>{result.text}</Descriptions.Item>
                <Descriptions.Item label={T.latency}>{result.elapsed} ms</Descriptions.Item>
              </Descriptions>
            }
            showIcon
          />
        )}
      </Card>
    </div>
  );
}
