import { Alert, Collapse, Descriptions, Table, Tag, Typography, Space } from 'antd'

const { Text, Paragraph } = Typography

const when = (iso) => (iso ? new Date(iso).toLocaleString() : '')

function Status({ title, source, children }) {
  if (!source) return <Alert type="info" showIcon message={`${title}: not fetched yet`} />
  if (!source.ok) return <Alert type="warning" showIcon message={`${title}: could not be fetched`} description={source.error} />
  return <Alert type="success" showIcon message={`${title}: fetched ${when(source.fetched_at)}`} description={children} />
}

export default function SourcesPanel({ run }) {
  const s = run.sources || {}
  const kg = s.kg
  const drive = s.drive
  const bucket = run.bucket?.summary
  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Status title="Knowledge Graph" source={kg}>
        {kg && (
          <Text>
            collab space {kg.space}: {kg.subjects} subjects, {kg.subject_groups} subject groups, {kg.tissue_samples} tissue samples,{' '}
            {kg.tissue_sample_collections} collections, {kg.people} persons
          </Text>
        )}
      </Status>

      <Status title="Collab drive" source={drive}>
        {drive && (
          <>
            <div>
              Library {drive.library}. Data descriptor: {drive.descriptor ? <Tag color="green">{drive.descriptor}</Tag> : <Tag color="red">not found</Tag>}{' '}
              Metadata draft: {drive.draft ? <Tag color="green">found</Tag> : <Tag color="red">not found</Tag>}
            </div>
            {drive.descriptor_error && <div><Text type="danger">{drive.descriptor_error}</Text></div>}
            {drive.draft_error && <div><Text type="danger">{drive.draft_error}</Text></div>}
          </>
        )}
      </Status>
      {drive?.ok && drive.files?.length > 0 && (
        <Text type="secondary">Files at the top of the drive: {drive.files.join(', ')}</Text>
      )}

      <Status title="Bucket" source={s.bucket}>
        {bucket && (
          <Text>
            {run.bucket.bucket}: {bucket.files}
            {bucket.truncated ? '+' : ''} files, {bucket.size}. Data descriptor PDF: {bucket.has_descriptor_pdf ? 'yes' : 'no'}; licence file:{' '}
            {bucket.has_license ? 'yes' : 'no'}
          </Text>
        )}
      </Status>

      <Collapse
        items={[
          run.descriptor && {
            key: 'dd',
            label: `Text of the data descriptor (${run.descriptor.name}, ${run.descriptor.text.length.toLocaleString()} characters)`,
            children: <Paragraph style={{ whiteSpace: 'pre-wrap', maxHeight: 420, overflow: 'auto' }}>{run.descriptor.text}</Paragraph>,
          },
          bucket && {
            key: 'bucket',
            label: 'Folders and file types in the bucket',
            children: (
              <>
                <Paragraph>
                  {Object.entries(bucket.extensions).slice(0, 25).map(([k, v]) => `.${k}: ${v}`).join(', ')}
                </Paragraph>
                <Table size="small" pagination={{ pageSize: 15 }} rowKey="path"
                  dataSource={bucket.folders}
                  columns={[
                    { title: 'Folder', dataIndex: 'path' },
                    { title: 'Files', dataIndex: 'files', width: 80 },
                    { title: 'Size', dataIndex: 'size', width: 100 },
                    { title: 'Examples', dataIndex: 'examples', render: (v) => v.join(', ') },
                  ]} />
              </>
            ),
          },
        ].filter(Boolean)}
      />
    </Space>
  )
}
