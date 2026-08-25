import "./globals.css";

export const metadata = {
  title: "StackAtlas — the context layer for AI agents",
  description:
    "Point it at a database. Get a living catalog: schema graph, AI-written docs, health signals, and an MCP server your agents can query.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
