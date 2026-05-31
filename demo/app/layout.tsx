import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'skim — Runtime LLM Token Intelligence',
  description: 'The missing layer between your AI tools and the LLM API. Strips waste in real-time, caches prompts automatically, shows live context fill %, and gives teams a cost dashboard — without changing a line of code.',
  keywords: 'LLM, tokens, Claude, OpenAI, cost optimization, prompt caching, context window, enterprise AI',
  openGraph: {
    title: 'skim — Runtime LLM Token Intelligence',
    description: 'One env var. Your AI tools stop wasting money.',
    type: 'website',
  },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
        <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js" async></script>
      </head>
      <body style={{ margin: 0 }}>{children}</body>
    </html>
  )
}
