/**
 * MarkdownRenderer Component
 *
 * Renders markdown content as formatted HTML for the chat interface.
 */

import Markdown, { defaultUrlTransform } from 'react-markdown'
import rehypeRaw from 'rehype-raw'
import remarkGfm from 'remark-gfm'
import { useState } from 'react'
import { Check, Copy } from 'lucide-react'
import type { Components } from 'react-markdown'
import { cn, copyToClipboard } from '../../lib/utils'

interface MarkdownRendererProps {
  content: string
  className?: string
}

// Code block with header (language + Copy) per design 03 "Code block".
function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    copyToClipboard(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="markdown__code-block">
      <div className="markdown__code-header">
        {language && <span className="markdown__code-lang">{language}</span>}
        <button
          type="button"
          onClick={handleCopy}
          className="markdown__code-copy"
          aria-label={copied ? 'Copied' : 'Copy code'}
          title={copied ? 'Copied' : 'Copy code'}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  )
}

const components: Components = {
  // Headings — styled via .markdown h1/h2/h3
  h1: ({ children }) => <h1>{children}</h1>,
  h2: ({ children }) => <h2>{children}</h2>,
  h3: ({ children }) => <h3>{children}</h3>,

  // Paragraphs
  p: ({ children }) => <p>{children}</p>,

  // Links — need target/rel attributes
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),

  // Lists
  ul: ({ children }) => <ul>{children}</ul>,
  ol: ({ children }) => <ol>{children}</ol>,
  li: ({ children }) => <li>{children}</li>,

  // Code — inline vs block detection + language label + copy
  code: ({ className, children }) => {
    const isInline = !className
    if (isInline) {
      return <code>{children}</code>
    }
    // Code block
    const match = /language-(\w+)/.exec(className || '')
    const language = match ? match[1] : ''
    return (
      <CodeBlock language={language} code={String(children)} />
    )
  },
  pre: ({ children }) => <>{children}</>,

  // Blockquote
  blockquote: ({ children }) => <blockquote>{children}</blockquote>,

  // Horizontal rule
  hr: () => <hr />,

  // Bold and italic
  strong: ({ children }) => <strong>{children}</strong>,
  em: ({ children }) => <em>{children}</em>,

  // Strikethrough
  del: ({ children }) => <del>{children}</del>,

  // Images — with audio data URI detection
  img: ({ src, alt, ...props }) => {
    if (src?.startsWith('data:audio/')) {
      return (
        <audio controls>
          <source src={src} type={src.split(';')[0].replace('data:', '')} />
        </audio>
      )
    }
    return <img src={src} alt={alt} {...props} />
  },

  // Tables (GitHub Flavored Markdown)
  table: ({ children }) => (
    <div className="markdown__table-wrap">
      <table>{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead>{children}</thead>,
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => <tr>{children}</tr>,
  th: ({ children }) => <th>{children}</th>,
  td: ({ children }) => <td>{children}</td>,
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={cn('markdown', className)}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeRaw]}
        components={components}
        urlTransform={(url) => url.startsWith('data:') ? url : defaultUrlTransform(url)}
      >
        {content}
      </Markdown>
    </div>
  )
}
