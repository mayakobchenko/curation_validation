import { useState } from 'react'
import { Form, Input, Button, Typography, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'

const { Title, Paragraph } = Typography

export default function NewValidation() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onFinish = async (values) => {
    setLoading(true)
    try {
      const run = await api.startRun(values)
      message.success('Pulled dataset version from the Knowledge Graph.')
      navigate(`/validations/${run.id}`)
    } catch (e) {
      message.error(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Title level={3}>Start a new curation validation</Title>
      <Paragraph type="secondary">
        This replaces opening the data descriptor, metadata overview, dataset preview, DSV in the KG Editor
        and the collab bucket as separate tabs — the dataset version's data is pulled straight from the
        Knowledge Graph below.
      </Paragraph>
      <Form form={form} layout="vertical" onFinish={onFinish} style={{ maxWidth: 480 }}>
        <Form.Item
          label="Dataset version UUID"
          name="dataset_version_uuid"
          rules={[{ required: true, message: 'Required' }]}
        >
          <Input placeholder="e.g. 7f78bf9f-...-cd6fx2q" />
        </Form.Item>
        <Form.Item label="Dataset title" name="dataset_title">
          <Input />
        </Form.Item>
        <Form.Item label="Primary curator" name="primary_curator_name">
          <Input />
        </Form.Item>
        <Form.Item label="GitLab issue URL" name="gitlab_issue_url">
          <Input />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={loading}>
          Pull from KG &amp; start validation
        </Button>
      </Form>
    </>
  )
}
