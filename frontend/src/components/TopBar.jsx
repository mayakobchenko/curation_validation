import { useEffect, useState } from 'react'
import { Layout, Button, Typography, Space } from 'antd'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

const { Header } = Layout
const { Text } = Typography

export default function TopBar() {
  const [user, setUser] = useState(null)

  useEffect(() => {
    api.me().then(setUser).catch(() => setUser(null))
  }, [])

  return (
    <Header style={{ background: '#fff', borderBottom: '1px solid #e8e8e8', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <Link to="/" style={{ fontWeight: 600, fontSize: 18, color: '#222' }}>
        EBRAINS Curation Validator
      </Link>
      <Space>
        {user && <Text>{user.name}</Text>}
        {user ? (
          <Button onClick={() => api.logout().then(() => window.location.reload())}>Log out</Button>
        ) : (
          <Button type="primary" href="/auth/login">Log in</Button>
        )}
      </Space>
    </Header>
  )
}
