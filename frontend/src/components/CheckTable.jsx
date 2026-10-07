import { Table, Radio, Input, Tag, Tooltip } from 'antd'
import { CheckCircleTwoTone, CloseCircleTwoTone, MinusCircleTwoTone } from '@ant-design/icons'

const autoIcon = (result) => {
  if (result === 'YES') return <CheckCircleTwoTone twoToneColor="#52c41a" />
  if (result === 'NO') return <CloseCircleTwoTone twoToneColor="#ff4d4f" />
  if (result === 'NA') return <MinusCircleTwoTone twoToneColor="#bfbfbf" />
  return null
}

export default function CheckTable({ items, onChange }) {
  const update = (index, patch) => {
    const next = items.map((it, i) => (i === index ? { ...it, ...patch } : it))
    onChange(next)
  }

  const columns = [
    { title: 'Item', dataIndex: 'label', key: 'label', width: '30%' },
    {
      title: 'Auto-check',
      key: 'auto',
      width: 90,
      render: (_, row) =>
        row.auto_result ? (
          <Tooltip title={row.auto_note || row.auto_result}>{autoIcon(row.auto_result)}</Tooltip>
        ) : (
          <Tag>manual</Tag>
        ),
    },
    {
      title: 'Answer',
      key: 'answer',
      width: 260,
      render: (_, row, index) => (
        <Radio.Group
          size="small"
          value={row.answer}
          onChange={(e) => update(index, { answer: e.target.value })}
        >
          <Radio.Button value="YES">Yes</Radio.Button>
          <Radio.Button value="NO">No</Radio.Button>
          <Radio.Button value="NA">N/A</Radio.Button>
          <Radio.Button value="PENDING">Pending</Radio.Button>
        </Radio.Group>
      ),
    },
    {
      title: 'Comment',
      key: 'comment',
      render: (_, row, index) => (
        <Input
          value={row.comment}
          onChange={(e) => update(index, { comment: e.target.value })}
          placeholder="Optional comment"
        />
      ),
    },
  ]

  return <Table rowKey="label" size="small" pagination={false} columns={columns} dataSource={items} />
}
