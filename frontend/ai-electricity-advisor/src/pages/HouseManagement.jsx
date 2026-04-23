import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, Popconfirm, Typography,
  Tag, Descriptions, Drawer, message, Empty, Skeleton, Card, Tooltip,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, EyeOutlined, HomeOutlined,
} from '@ant-design/icons';
import { houseApi } from '../api/client';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';

const { Title, Text } = Typography;

export default function HouseManagement() {
  const { user } = useAuth();
  const { T, isRtl } = useLang();
  const refreshTimerRef = useRef(null);

  const [houses, setHouses] = useState([]);
  const [loading, setLoading] = useState(true);

  // Modal state
  const [addOpen, setAddOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [viewOpen, setViewOpen] = useState(false);
  const [selectedHouse, setSelectedHouse] = useState(null);
  const [saving, setSaving] = useState(false);

  const [addForm] = Form.useForm();
  const [editForm] = Form.useForm();

  const fetchHouses = useCallback(async ({ background = false } = {}) => {
    if (!background) {
      setLoading(true);
    }

    try {
      const data = await houseApi.list(user.national_id);
      setHouses(Array.isArray(data) ? data : []);
    } catch (err) {
      message.error(err.message);
    } finally {
      if (!background) {
        setLoading(false);
      }
    }
  }, [user.national_id]);

  useEffect(() => { fetchHouses(); }, [fetchHouses]);

  const refreshHouses = useCallback(async () => {
    await fetchHouses();

    if (refreshTimerRef.current) {
      window.clearTimeout(refreshTimerRef.current);
    }

    // A second fetch helps when the backend store lags briefly behind the mutation response.
    refreshTimerRef.current = window.setTimeout(() => {
      fetchHouses({ background: true });
    }, 700);
  }, [fetchHouses]);

  useEffect(() => () => {
    if (refreshTimerRef.current) {
      window.clearTimeout(refreshTimerRef.current);
    }
  }, []);

  // Add house
  const handleAdd = async (values) => {
    setSaving(true);
    try {
      await houseApi.create(user.national_id, values.house_id, values.address);
      message.success(T.houseAdded);
      setAddOpen(false);
      addForm.resetFields();
      await refreshHouses();
    } catch (err) {
      message.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  // Edit house
  const openEdit = (house) => {
    setSelectedHouse(house);
    editForm.setFieldsValue({ address: house.address });
    setEditOpen(true);
  };

  const handleEdit = async (values) => {
    setSaving(true);
    try {
      await houseApi.update(user.national_id, selectedHouse.house_id, values.address);
      message.success(T.houseSaved);
      setEditOpen(false);
      await refreshHouses();
    } catch (err) {
      message.error(err.message);
    } finally {
      setSaving(false);
    }
  };

  // Delete house
  const handleDelete = async (house) => {
    try {
      await houseApi.remove(user.national_id, house.house_id);
      message.success(T.houseDeleted);
      await refreshHouses();
    } catch (err) {
      message.error(err.message);
    }
  };

  // View house
  const openView = (house) => {
    setSelectedHouse(house);
    setViewOpen(true);
  };

  const columns = [
    {
      title: T.houseId,
      dataIndex: 'house_id',
      key: 'house_id',
      render: (id) => <Tag color="blue" icon={<HomeOutlined />}>{id}</Tag>,
    },
    {
      title: T.address,
      dataIndex: 'address',
      key: 'address',
      ellipsis: true,
    },
    {
      title: T.createdAt,
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v) => v ? new Date(v).toLocaleDateString() : '—',
      width: 140,
    },
    {
      title: T.actions,
      key: 'actions',
      width: 160,
      render: (_, house) => (
        <Space size={6}>
          <Tooltip title={T.view}>
            <Button
              type="text"
              icon={<EyeOutlined />}
              size="small"
              style={{ color: '#1677ff' }}
              onClick={() => openView(house)}
            />
          </Tooltip>
          <Tooltip title={T.edit}>
            <Button
              type="text"
              icon={<EditOutlined />}
              size="small"
              style={{ color: '#52c41a' }}
              onClick={() => openEdit(house)}
            />
          </Tooltip>
          <Tooltip title={T.delete}>
            <Popconfirm
              title={T.confirmDelete}
              onConfirm={() => handleDelete(house)}
              okText={T.yes}
              cancelText={T.no}
              okButtonProps={{ danger: true }}
            >
              <Button
                type="text"
                icon={<DeleteOutlined />}
                size="small"
                danger
              />
            </Popconfirm>
          </Tooltip>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ direction: isRtl ? 'rtl' : 'ltr' }}>
      <Card
        title={
          <Space>
            <HomeOutlined />
            <Title level={4} style={{ margin: 0 }}>{T.navHouses}</Title>
          </Space>
        }
        extra={
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setAddOpen(true)}
          >
            {T.addHouse}
          </Button>
        }
        style={{ borderRadius: 12 }}
      >
        {loading ? (
          <Skeleton active />
        ) : houses.length === 0 ? (
          <Empty description={T.noHouses}>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setAddOpen(true)}>
              {T.addHouse}
            </Button>
          </Empty>
        ) : (
          <Table
            dataSource={houses}
            columns={columns}
            rowKey="house_id"
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
            scroll={{ x: true }}
          />
        )}
      </Card>

      {/* Add Modal */}
      <Modal
        title={T.addHouse}
        open={addOpen}
        onCancel={() => { setAddOpen(false); addForm.resetFields(); }}
        footer={null}
        destroyOnClose
      >
        <Form form={addForm} layout="vertical" onFinish={handleAdd} size="large" style={{ marginTop: 12 }}>
          <Form.Item
            name="house_id"
            label={T.houseId}
            extra={T.houseIdHint}
            rules={[{ required: true, message: T.houseId }]}
          >
            <Input placeholder="H001" />
          </Form.Item>
          <Form.Item
            name="address"
            label={T.address}
            rules={[{ required: true, message: T.address }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
              <Button onClick={() => { setAddOpen(false); addForm.resetFields(); }}>{T.cancel}</Button>
              <Button type="primary" htmlType="submit" loading={saving}>{T.save}</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit Modal */}
      <Modal
        title={`${T.edit}: ${selectedHouse?.house_id}`}
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical" onFinish={handleEdit} size="large" style={{ marginTop: 12 }}>
          <Form.Item
            name="address"
            label={T.address}
            rules={[{ required: true }]}
          >
            <Input.TextArea rows={3} />
          </Form.Item>
          <Form.Item style={{ marginBottom: 0 }}>
            <Space style={{ justifyContent: 'flex-end', width: '100%' }}>
              <Button onClick={() => setEditOpen(false)}>{T.cancel}</Button>
              <Button type="primary" htmlType="submit" loading={saving}>{T.save}</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* View Drawer */}
      <Drawer
        title={`${T.view}: ${selectedHouse?.house_id}`}
        open={viewOpen}
        onClose={() => setViewOpen(false)}
        placement={isRtl ? 'left' : 'right'}
        width={360}
      >
        {selectedHouse && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label={T.houseId}>{selectedHouse.house_id}</Descriptions.Item>
            <Descriptions.Item label={T.address}>{selectedHouse.address}</Descriptions.Item>
            <Descriptions.Item label={T.createdAt}>
              {selectedHouse.created_at ? new Date(selectedHouse.created_at).toLocaleString() : '—'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}
