import { td } from './statsTheme'

/**
 * @param {{ columns: { key: string, label: string, render?: (row) => React.ReactNode }[], rows: object[], empty?: string }}
 */
export default function MiniTable({ columns, rows, empty = 'No data.' }) {
  if (!rows?.length) {
    return <p style={{ color: '#9aa0a6', fontSize: 14, margin: 0 }}>{empty}</p>
  }
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr style={{ borderBottom: '1px solid #2a2d3a', textAlign: 'left' }}>
          {columns.map(c => (
            <th key={c.key} style={{ ...td, color: '#9aa0a6', fontWeight: 500 }}>{c.label}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={row.id ?? row.key ?? i} style={{ borderBottom: '1px solid #1a1d27' }}>
            {columns.map(c => (
              <td key={c.key} style={td}>
                {c.render ? c.render(row) : row[c.key]}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
