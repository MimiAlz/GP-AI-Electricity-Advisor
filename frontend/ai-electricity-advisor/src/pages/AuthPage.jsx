import { useState } from "react";
import {
  Card,
  Form,
  Input,
  Button,
  Typography,
  Alert,
  Tabs,
  message,
} from "antd";
import { UserOutlined, LockOutlined, IdcardOutlined } from "@ant-design/icons";
import { authApi } from "../api/client";
import { useAuth } from "../contexts/AuthContext";
import { useLang } from "../contexts/LangContext";

const { Title, Text } = Typography;

function LoginForm() {
  const { T } = useLang();
  const { login } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const onFinish = async ({ identifier, password }) => {
    setLoading(true);
    setError("");
    try {
      const data = await authApi.login(identifier, password);
      message.success(T.loginSuccess);
      login(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form layout="vertical" onFinish={onFinish} size="large">
      {error && (
        <Alert
          message={error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}
      <Form.Item
        name="identifier"
        label={T.identifier}
        rules={[{ required: true, message: T.identifier }]}
      >
        <Input prefix={<UserOutlined />} placeholder={T.identifier} />
      </Form.Item>
      <Form.Item
        name="password"
        label={T.password}
        rules={[{ required: true, message: T.password }]}
      >
        <Input.Password prefix={<LockOutlined />} placeholder={T.password} />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>
          {T.loginBtn}
        </Button>
      </Form.Item>
    </Form>
  );
}

function SignupForm() {
  const { T } = useLang();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const onFinish = async ({ national_id, username, password }) => {
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      await authApi.signup(national_id, username, password);
      setSuccess(T.signupSuccess);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Form layout="vertical" onFinish={onFinish} size="large">
      {error && (
        <Alert
          message={error}
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}
      {success && (
        <Alert
          message={success}
          type="success"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}
      <Form.Item
        name="national_id"
        label={T.nationalId}
        rules={[
          { required: true },
          { pattern: /^\d{10}$/, message: T.nationalIdHint },
        ]}
      >
        <Input
          prefix={<IdcardOutlined />}
          placeholder="0000000000"
          maxLength={10}
        />
      </Form.Item>
      <Form.Item
        name="username"
        label={T.username}
        rules={[{ required: true }]}
      >
        <Input prefix={<UserOutlined />} />
      </Form.Item>
      <Form.Item
        name="password"
        label={T.password}
        rules={[{ required: true, min: 6 }]}
      >
        <Input.Password prefix={<LockOutlined />} />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit" loading={loading} block>
          {T.registerBtn}
        </Button>
      </Form.Item>
    </Form>
  );
}

export default function AuthPage() {
  const { T, isRtl } = useLang();

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "linear-gradient(135deg, #0f0c29, #302b63, #24243e)",
        direction: isRtl ? "rtl" : "ltr",
      }}
    >
      <Card
        style={{
          width: 420,
          borderRadius: 16,
          boxShadow: "0 20px 60px rgba(0,0,0,0.4)",
        }}
        styles={{ body: { padding: 36 } }}
      >
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <Title level={2} style={{ margin: 0 }}>
            {" "}
            <img width={38} src="favicon.svg" alt="Logo" /> {T.appTitle}
          </Title>
        </div>
        <Tabs
          centered
          items={[
            { key: "login", label: T.login, children: <LoginForm /> },
            { key: "signup", label: T.signup, children: <SignupForm /> },
          ]}
        />
      </Card>
    </div>
  );
}
