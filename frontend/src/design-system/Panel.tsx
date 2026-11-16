import type { ReactNode } from 'react'

interface PanelProps {
  title: string
  /** Right-aligned header content: counts, timestamps, badges. */
  meta?: ReactNode
  children: ReactNode
  className?: string
  /** Body scrolls internally instead of growing the page. */
  scroll?: boolean
  /** Remove body padding (for edge-to-edge content like images). */
  flush?: boolean
  footer?: ReactNode
}

export function Panel({ title, meta, children, className, scroll, flush, footer }: PanelProps) {
  const id = `panel-${title.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`
  return (
    <section className={['ds-panel', className].filter(Boolean).join(' ')} aria-labelledby={id}>
      <header className="ds-panel__header">
        <h2 id={id} className="label">
          {title}
        </h2>
        {meta !== undefined && <div className="ds-panel__meta">{meta}</div>}
      </header>
      <div
        className={[
          'ds-panel__body',
          scroll ? 'ds-panel__body--scroll' : '',
          flush ? 'ds-panel__body--flush' : '',
        ]
          .filter(Boolean)
          .join(' ')}
      >
        {children}
      </div>
      {footer !== undefined && <footer className="ds-panel__footer">{footer}</footer>}
    </section>
  )
}
