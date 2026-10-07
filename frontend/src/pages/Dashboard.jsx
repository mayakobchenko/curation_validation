import { useEffect, useState } from 'react'
import { Table, Button, Tag, Typography, Space } from 'antd'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

const { Title } = Typography

export default function Dashboard() {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.listRuns().then(setRuns).catch(() => {}).finally(() => setLoading(false))
  }, [])

  const columns = [
    { title: 'Dataset', dataIndex: ['dataset_info', 'dataset_title'], key: 'title' },
    { title: 'DSV UUID', dataIndex: ['dataset_info', 'dataset_version_uuid'], key: 'dsv' },
    { title: 'Primary curator', dataIndex: ['dataset_info', 'primary_curator_name'], key: 'primary' },
    { title: 'Created', dataIndex: 'created_at', key: 'created_at' },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (s) => <Tag color={s === 'submitted' ? 'green' : 'gold'}>{s}</Tag>,
    },
    {
      title: '',
      key: 'open',
      render: (_, run) => <Link to={`/validations/${run.id}`}>Open</Link>,
    },
  ]

  return (
    <>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Validation runs</Title>
        <Link to="/new"><Button type="primary">Start new validation</Button></Link>
      </Space>
      <Table rowKey="id" loading={loading} columns={columns} dataSource={runs} />
    </>
  )
}
