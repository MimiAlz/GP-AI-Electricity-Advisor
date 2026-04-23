import { useState } from 'react';
import { Layout, Menu, Button, Avatar, Dropdown, Space, Typography, Switch, Tag } from 'antd';
import {
  HomeOutlined,
  ThunderboltOutlined,
  LineChartOutlined,
  ApiOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  UserOutlined,
  GlobalOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useLang } from '../contexts/LangContext';

const { Header, Sider, Content, Footer } = Layout;
const { Text } = Typography;

const NAV_ITEMS = [
  { key: '/houses',        icon: <HomeOutlined />,      labelKey: 'navHouses' },
  { key: '/forecast',      icon: <LineChartOutlined />, labelKey: 'navForecast' },
  { key: '/profile',       icon: <UserOutlined />,      labelKey: 'navProfile' },
//   { key: '/disaggregation', icon: <ThunderboltOutlined />, labelKey: 'navDisaggregation' },
//   { key: '/area-forecast', icon: <AreaChartOutlined />, labelKey: 'navAreaForecast' },
//   { key: '/backend-test', icon: <ApiOutlined />, labelKey: 'navBackendTest' },
];

export default function AppLayout({ children }) {
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout } = useAuth();
  const { T, lang, toggle, isRtl } = useLang();
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = NAV_ITEMS.map(({ key, icon, labelKey }) => ({
    key,
    icon,
    label: T[labelKey],
  }));

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: T.logout,
      danger: true,
    },
  ];

  const handleMenuClick = ({ key }) => navigate(key);
  const handleUserMenu = ({ key }) => {
    if (key === 'logout') logout();
  };

  return (
    <Layout style={{ minHeight: '100vh', direction: isRtl ? 'rtl' : 'ltr' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        trigger={null}
        width={220}
        style={{
          background: '#0f0c29',
          boxShadow: isRtl ? '-2px 0 8px rgba(0,0,0,0.3)' : '2px 0 8px rgba(0,0,0,0.3)',
          position: 'fixed',
          height: '100vh',
          insetInlineStart: 0,
          top: 0,
          zIndex: 100,
          overflowY: 'auto',
        }}
      >
        {/* Logo / Brand */}
        <div
          style={{
            height: 64,
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            padding: collapsed ? '0' : '0 20px',
            borderBottom: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <span style={{ fontSize: 22 }}><img width={35} src="favicon.svg" alt="Logo" /></span>
          {!collapsed && (
            <Text
              style={{
                color: '#fff',
                fontWeight: 700,
                fontSize: 15,
                marginInlineStart: 10,
                whiteSpace: 'nowrap',
                overflow: 'hidden',
              }}
            >
              {T.appTitle}
            </Text>
          )}
        </div>

        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{
            background: 'transparent',
            border: 'none',
            marginTop: 8,
          }}
        />
      </Sider>

      <Layout
        style={{
          marginInlineStart: collapsed ? 80 : 220,
          transition: 'margin 0.2s',
        }}
      >
        {/* Header */}
        <Header
          style={{
            padding: '0 24px',
            background: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            boxShadow: '0 1px 4px rgba(0,0,0,0.12)',
            position: 'sticky',
            top: 0,
            zIndex: 99,
          }}
        >
          {/* Left: collapse button */}
          <Button
            type="text"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: 18, width: 40, height: 40 }}
          />

          {/* Right: Lang toggle + User avatar */}
          <Space size={16}>
            <Space size={8}>
              <GlobalOutlined style={{ color: '#666' }} />
              <Switch
                checkedChildren="AR"
                unCheckedChildren="EN"
                checked={lang === 'ar'}
                onChange={toggle}
                style={{ background: lang === 'ar' ? '#302b63' : undefined }}
              />
            </Space>

            <Dropdown
              menu={{ items: userMenuItems, onClick: handleUserMenu }}
              placement={isRtl ? 'bottomLeft' : 'bottomRight'}
            >
              <Space style={{ cursor: 'pointer' }}>
                <Avatar
                  icon={<UserOutlined />}
                  style={{ background: 'linear-gradient(135deg, #0f0c29, #302b63)' }}
                />
                <Text style={{ maxWidth: 120, overflow: 'hidden', whiteSpace: 'nowrap' }}>
                  {user?.username}
                </Text>
              </Space>
            </Dropdown>
          </Space>
        </Header>

        {/* Page content */}
        <Content style={{ margin: '24px', minHeight: 'calc(100vh - 64px - 70px)' }}>
          {children}
        </Content>

        <Footer style={{ textAlign: 'center', color: '#aaa', fontSize: 13 }}>
          <img width={23} src="secondLogo.svg" alt="Logo" /> {T.appTitle} © {new Date().getFullYear()}
        </Footer>
      </Layout>
    </Layout>
  );
}
