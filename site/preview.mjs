// Look at dist/ on this Mac, served the way Cloudflare serves it: `/a/b` finds `a/b.html`, `/a/` finds
// `a/index.html` (and `/a` goes to `/a/`), `_redirects` applies, and anything else gets 404.html.
//   node preview.mjs [port]   (default 5612)

import fs from 'node:fs'
import http from 'node:http'
import path from 'node:path'

const DIST = path.join(import.meta.dirname, 'dist')
const PORT = Number(process.argv[2] ?? 5612)
const TYPES = { '.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.ico': 'image/x-icon', '.txt': 'text/plain; charset=utf-8', '.md': 'text/markdown; charset=utf-8' }
const REDIRECTS = new Map(
  fs.readFileSync(path.join(DIST, '_redirects'), 'utf8').split('\n').filter(Boolean).map((l) => l.split(' ').slice(0, 2)),
)
const isFile = (f) => fs.existsSync(f) && fs.statSync(f).isFile()

http
  .createServer((req, res) => {
    const url = decodeURIComponent(new URL(req.url, 'http://x').pathname)
    const send = (status, file) => {
      res.writeHead(status, { 'content-type': TYPES[path.extname(file)] ?? 'application/octet-stream' })
      fs.createReadStream(file).pipe(res)
    }
    if (REDIRECTS.has(url)) return res.writeHead(301, { location: REDIRECTS.get(url) }).end()
    const local = path.join(DIST, url)
    if (!local.startsWith(DIST)) return res.writeHead(400).end()
    if (url.endsWith('/') && isFile(path.join(local, 'index.html'))) return send(200, path.join(local, 'index.html'))
    if (!url.endsWith('/') && isFile(local)) return send(200, local)
    if (!url.endsWith('/') && isFile(`${local}.html`)) return send(200, `${local}.html`)
    if (!url.endsWith('/') && isFile(path.join(local, 'index.html'))) return res.writeHead(307, { location: `${url}/` }).end()
    if (url.endsWith('/') && url !== '/' && isFile(`${local.replace(/\/$/, '')}.html`)) return res.writeHead(307, { location: url.replace(/\/$/, '') }).end()
    send(404, path.join(DIST, '404.html'))
  })
  .listen(PORT, '127.0.0.1', () => console.log(`MiCodex preview: http://127.0.0.1:${PORT}/`))
