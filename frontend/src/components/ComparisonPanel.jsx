import { useState } from 'react'
import { Alert, Switch, Table, Tag, Space, Typography } from 'antd'

const { Text } = Typography

const STATUS = {
  match: { color: 'green', text: 'same' },
  differs: { color: 'red', text: 'differs' },
  only_in_draft: { color: 'orange', text: 'only in the draft / bucket' },
  only_in_kg: { color: 'volcano', text: 'only in the KG' },
}

function Findings({ title, block, hint }) {
  const [onlyDiffs, setOnlyDiffs] = useState(true)
  if (!block) return null
  const rows = block.findings.filter((f) => !onlyDiffs || f.status !== 'match')
  return (
    <div style={{ marginBottom: 24 }}>
      <Space style={{ marginBottom: 8 }} wrap>
        <Text strong>{title}</Text>
        {Object.entries(block.counts).map(([k, v]) => <Tag key={k} color={STATUS[k].color}>{STATUS[k].text}: {v}</Tag>)}
        <Switch size="small" checked={onlyDiffs} onChange={setOnlyDiffs} /> <Text type="secondary">only differences</Text>
      </Space>
      {hint && <div><Text type="secondary">{hint}</Text></div>}
      <Table size="small" rowKey={(r) => `${r.area}|${r.item}|${r.status}`} dataSource={rows} pagination={{ pageSize: 20 }}
        columns={[
          { title: 'Area', dataIndex: 'area', width: 190 },
          { title: 'Item', dataIndex: 'item' },
          { title: '', dataIndex: 'status', width: 190, render: (s) => <Tag color={STATUS[s].color}>{STATUS[s].text}</Tag> },
          { title: 'Draft / bucket', dataIndex: 'draft', ellipsis: true },
          { title: 'Knowledge Graph', dataIndex: 'kg', ellipsis: true },
        ]} />
    </div>
  )
}

export default function ComparisonPanel({ run }) {
  const cmp = run.comparison || {}
  const bucketBlock = cmp.bucket?.length
    ? { counts: cmp.bucket.reduce((a, f) => ({ ...a, [f.status]: (a[f.status] || 0) + 1 }), { match: 0, differs: 0, only_in_draft: 0, only_in_kg: 0 }), findings: cmp.bucket }
    : null
  return (
    <>
      {!cmp.draft && (
        <Alert type="info" showIcon style={{ marginBottom: 16 }}
          message="No metadata draft to compare"
          description="The Collab drive holds no metadata_wizard_draft.json, or the drive could not be read (see Sources)." />
      )}
      <Findings title="Metadata draft in the Collab drive against the Knowledge Graph" block={cmp.draft}
        hint="“Only in the draft” was submitted but is not in the KG; “only in the KG” is in the KG but not in the draft." />
      <Findings title="Subjects in the bucket against the Knowledge Graph" block={bucketBlock}
        hint="Identifiers like sub-01 in folder and file names of the bucket." />
    </>
  )
}
