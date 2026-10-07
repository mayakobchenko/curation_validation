import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { Typography, Tabs, Button, Space, message, Spin, Input, Form } from 'antd'
import { api } from '../api.js'
import CheckTable from '../components/CheckTable.jsx'

const { Title, Paragraph } = Typography

export default function ValidationForm() {
  const { id } = useParams()
  const [run, setRun] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    api.getRun(id).then(setRun).catch((e) => message.error(e.message)).finally(() => setLoading(false))
  }, [id])

  useEffect(() => { load() }, [load])

  const save = async (patch) => {
    setSaving(true)
    try {
      const updated = await api.updateRun(id, { ...run, ...patch })
      setRun(updated)
    } catch (e) {
      message.error(e.message)
    } finally {
      setSaving(false)
    }
  }

  const refresh = async () => {
    try {
      const updated = await api.refreshChecks(id)
      setRun(updated)
      message.success('Re-pulled KG data and re-ran mechanical checks.')
    } catch (e) {
      message.error(e.message)
    }
  }

  const submit = async () => {
    const updated = await api.submitRun(id)
    setRun(updated)
    message.success('Validation marked as submitted.')
  }

  if (loading || !run) return <Spin style={{ marginTop: 48 }} />

  const items = [
    {
      key: 'dataDescriptor',
      label: '3. Data Descriptor',
      children: (
        <CheckTable
          items={run.data_descriptor_checks.items}
          onChange={(next) => save({ data_descriptor_checks: { ...run.data_descriptor_checks, items: next } })}
        />
      ),
    },
    {
      key: 'structure',
      label: '4. Structure & file storage',
      children: (
        <CheckTable
          items={run.structure_checks.items}
          onChange={(next) => save({ structure_checks: { ...run.structure_checks, items: next } })}
        />
      ),
    },
    {
      key: 'dsDsv',
      label: '5a. Dataset / DSV',
      children: (
        <CheckTable
          items={run.kge_metadata_checks.dataset_and_version}
          onChange={(next) =>
            save({ kge_metadata_checks: { ...run.kge_metadata_checks, dataset_and_version: next } })
          }
        />
      ),
    },
    {
      key: 'subjects',
      label: '5b. Subjects',
      children: (
        <CheckTable
          items={run.kge_metadata_checks.subjects}
          onChange={(next) => save({ kge_metadata_checks: { ...run.kge_metadata_checks, subjects: next } })}
        />
      ),
    },
    {
      key: 'tissue',
      label: '5c. Tissue samples',
      children: (
        <CheckTable
          items={run.kge_metadata_checks.tissue_samples}
          onChange={(next) =>
            save({ kge_metadata_checks: { ...run.kge_metadata_checks, tissue_samples: next } })
          }
        />
      ),
    },
    {
      key: 'project',
      label: '5d. Project',
      children: (
        <CheckTable
          items={run.kge_metadata_checks.project}
          onChange={(next) => save({ kge_metadata_checks: { ...run.kge_metadata_checks, project: next } })}
        />
      ),
    },
    {
      key: 'fileRepo',
      label: '6. File repository',
      children: (
        <CheckTable
          items={run.file_repository_checks.items}
          onChange={(next) => save({ file_repository_checks: { ...run.file_repository_checks, items: next } })}
        />
      ),
    },
  ]

  return (
    <>
      <Title level={3}>{run.dataset_info.dataset_title || 'Untitled dataset'}</Title>
      <Paragraph type="secondary">
        DSV {run.dataset_info.dataset_version_uuid} — status: {run.status}
        {saving && ' — saving…'}
      </Paragraph>

      <Form layout="vertical" style={{ maxWidth: 480, marginBottom: 16 }}>
        <Form.Item label="Secondary curator">
          <Input
            value={run.secondary_curator_info.secondary_curator_name}
            onChange={(e) =>
              save({
                secondary_curator_info: {
                  ...run.secondary_curator_info,
                  secondary_curator_name: e.target.value,
                },
              })
            }
          />
        </Form.Item>
      </Form>

      <Space style={{ marginBottom: 16 }}>
        <Button onClick={refresh}>Re-pull KG data &amp; re-run checks</Button>
        <Button type="primary" onClick={submit} disabled={run.status === 'submitted'}>
          Submit validation
        </Button>
        <Button href={api.exportDocxUrl(id)} target="_blank">Export .docx</Button>
        <Button href={api.exportPdfUrl(id)} target="_blank">Export .pdf</Button>
      </Space>

      <Tabs items={items} />
    </>
  )
}
