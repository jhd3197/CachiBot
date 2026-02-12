/**
 * MarkdownRenderer Component
 *
 * Renders markdown content as formatted HTML for the chat interface.
 */

import Markdown, { defaultUrlTransform } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'
import { cn } from '../../lib/utils'

interface MarkdownRendererProps {
  content: string
  className?: string
}

const components: Components = {
  // Headings
  h1: ({ children }) => (
    <h1 className="mb-4 mt-6 text-xl font-bold text-zinc-100 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-3 mt-5 text-lg font-bold text-zinc-100 first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-4 text-base font-bold text-zinc-100 first:mt-0">{children}</h3>
  ),

  // Paragraphs
  p: ({ children }) => (
    <p className="mb-3 leading-relaxed text-zinc-100 last:mb-0">{children}</p>
  ),

  // Links
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-cachi-400 underline decoration-cachi-400/50 underline-offset-2 hover:text-cachi-300 hover:decoration-cachi-300"
    >
      {children}
    </a>
  ),

  // Lists
  ul: ({ children }) => (
    <ul className="mb-3 ml-4 list-disc space-y-1 text-zinc-100 last:mb-0">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-3 ml-4 list-decimal space-y-1 text-zinc-100 last:mb-0">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="text-zinc-100">{children}</li>
  ),

  // Code
  code: ({ className, children, ...props }) => {
    const isInline = !className
    if (isInline) {
      return (
        <code className="rounded bg-zinc-700/50 px-1.5 py-0.5 font-mono text-sm text-cachi-300">
          {children}
        </code>
      )
    }
    // Code block
    const match = /language-(\w+)/.exec(className || '')
    const language = match ? match[1] : ''
    return (
      <div className="relative my-3">
        {language && (
          <div className="absolute right-2 top-2 rounded bg-zinc-700 px-2 py-0.5 text-xs text-zinc-400">
            {language}
          </div>
        )}
        <pre className="overflow-x-auto rounded-lg bg-zinc-900 p-4">
          <code className={cn('font-mono text-sm text-zinc-300', className)} {...props}>
            {children}
          </code>
        </pre>
      </div>
    )
  },
  pre: ({ children }) => <>{children}</>,

  // Blockquote
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-4 border-cachi-500/50 pl-4 italic text-zinc-400">
      {children}
    </blockquote>
  ),

  // Horizontal rule
  hr: () => <hr className="my-4 border-zinc-700" />,

  // Bold and italic
  strong: ({ children }) => (
    <strong className="font-bold text-zinc-100">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-zinc-200">{children}</em>
  ),

  // Strikethrough
  del: ({ children }) => (
    <del className="text-zinc-500 line-through">{children}</del>
  ),

  // Images — with audio data URI detection
  img: ({ src, alt, ...props }) => {
    if (src?.startsWith('data:audio/')) {
      return (
        <audio controls className="my-2 w-full max-w-md">
          <source src={src} type={src.split(';')[0].replace('data:', '')} />
        </audio>
      )
    }
    return <img src={src} alt={alt} className="my-3 max-w-full rounded-lg" {...props} />
  },

  // Tables (GitHub Flavored Markdown)
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto">
      <table className="min-w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="border-b border-zinc-700 bg-zinc-800/50">{children}</thead>
  ),
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => (
    <tr className="border-b border-zinc-800">{children}</tr>
  ),
  th: ({ children }) => (
    <th className="px-3 py-2 text-left font-medium text-zinc-300">{children}</th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-zinc-100">{children}</td>
  ),
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={cn('prose prose-invert prose-sm max-w-none', className)}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={components}
        urlTransform={(url) => url.startsWith('data:') ? url : defaultUrlTransform(url)}
      >
        {content}
      </Markdown>
    </div>
  )
}
