import { useEffect, useState } from 'react'
import { Alert, Button, Table, Tag, Typography, message } from 'antd'
import { api } from '../api.js'

const { Paragraph, Text } = Typography
const VERDICT = { ok: ['green', 'consistent'], issue: ['red', 'issue'], unclear: ['default', 'unclear'] }

export default function ReviewPanel({ run, onRun }) {
  const [llm, setLlm] = useState(null)
  const [busy, setBusy] = useState(false)
  useEffect(() => { api.llmInfo().then(setLlm).catch(() => setLlm({ available: false })) }, [])

  const start = async () => {
    setBusy(true)
    try {
      onRun(await api.llmReview(run.id))
      message.success('The review is ready.')
    } catch (e) {
      message.error(e.message)
    } finally {
      setBusy(false)
    }
  }

  const review = run.llm_review
  const hasText = !!run.descriptor?.text
  return (
    <>
      <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message="The model reads the data descriptor and checks it against the Knowledge Graph metadata and the bucket"
        description={
          <>
            It compares title, abstract, persons, subjects, tissue samples, techniques, licence and the file organisation, and looks for
            template text and typos. What is sent to {llm?.label || 'the language model service'}: the text of the data descriptor, the metadata of
            the collab space in the KG, the differences found against the metadata draft, and the <b>file names</b> of the bucket (no file contents).
            The result is a set of <b>suggestions</b>: your own Yes/No answers are never changed.
          </>
        } />
      {llm && !llm.available && <Alert type="warning" showIcon style={{ marginBottom: 16 }} message="No language model is configured for this deployment (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL)." />}
      {!hasText && <Alert type="warning" showIcon style={{ marginBottom: 16 }} message="There is no data descriptor text yet: fetch the data descriptor from the Collab drive first (see Sources)." />}
      <Button type="primary" loading={busy} disabled={!llm?.available || !hasText} onClick={start}>
        {review ? 'Run the review again' : `Review with ${llm?.label || 'the language model'}`}
      </Button>
      {busy && <Text type="secondary" style={{ marginLeft: 12 }}>This can take a minute or two…</Text>}

      {review && (
        <div style={{ marginTop: 24 }}>
          <Paragraph type="secondary">
            {review.service} ({review.model}), {new Date(review.created_at).toLocaleString()}
          </Paragraph>
          <Paragraph>{review.summary}</Paragraph>
          <Table size="small" pagination={false} rowKey={(r) => `${r.area}|${r.item}`} dataSource={review.findings}
            columns={[
              { title: 'Area', dataIndex: 'area', width: 150 },
              { title: '', dataIndex: 'verdict', width: 110, render: (v) => <Tag color={VERDICT[v][0]}>{VERDICT[v][1]}</Tag> },
              { title: 'Checked', dataIndex: 'item' },
              { title: 'Evidence', dataIndex: 'evidence' },
              { title: 'Suggestion', dataIndex: 'suggestion' },
            ]} />
          <Paragraph type="secondary" style={{ marginTop: 8 }}>
            AI suggestions can be wrong. They are shown next to the items of Table 3 as “AI suggestion”; check the evidence yourself.
          </Paragraph>
        </div>
      )}
    </>
  )
}
