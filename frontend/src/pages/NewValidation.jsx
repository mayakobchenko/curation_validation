import { useState } from 'react'
import { Form, Input, Button, Typography, message, Alert } from 'antd'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'

const { Title, Paragraph } = Typography
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export default function NewValidation() {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const onFinish = async (values) => {
    setLoading(true)
    try {
      const run = await api.startRun({
        dataset_version_uuid: values.dataset_version_uuid.trim(),
        gitlab_issue_url: (values.gitlab_issue_url || '').trim(),
      })
      message.success('Fetched the dataset version from the Knowledge Graph, the Collab drive and the bucket.')
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
        Enter the dataset version and the GitLab issue of the curation. Everything else is fetched for you: the title,
        dataset and version, persons and ORCIDs, subjects, subject groups, tissue samples and collections and all other
        metadata of the collab space in the Knowledge Graph; the data descriptor and the metadata draft from the Collab
        drive; and the file names of the bucket.
      </Paragraph>
      <Form form={form} layout="vertical" onFinish={onFinish} style={{ maxWidth: 560 }}>
        <Form.Item
          label="Dataset version UUID"
          name="dataset_version_uuid"
          rules={[
            { required: true, message: 'Required' },
            { pattern: UUID, message: 'Not a UUID, e.g. 724d4af0-fe28-4032-8837-120b0d64a81c' },
          ]}
        >
          <Input placeholder="724d4af0-fe28-4032-8837-120b0d64a81c" />
        </Form.Item>
        <Form.Item label="GitLab issue URL" name="gitlab_issue_url">
          <Input placeholder="https://gitlab.ebrains.eu/…/-/issues/1913" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={loading}>
          Fetch data &amp; start validation
        </Button>
        {loading && (
          <Alert style={{ marginTop: 16 }} type="info" showIcon
            message="Fetching from the Knowledge Graph, the Collab drive and the bucket"
            description="This can take up to a minute for a dataset with many subjects." />
        )}
      </Form>
    </>
  )
}
