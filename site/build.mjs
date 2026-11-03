// Builds codex.miberarave.xyz: every page of the codex as a 2004 lore wiki (MediaWiki's MonoBook look), from the
// codex's own files. gumi, 2026-11-03: "CLASSIC WIKI YESSS", every page, MiParcels too; the plan and her answers
// are in site/redesign/PLAN.md. A page's address is its file's path without `.md` (`miberas/0420.md` is `/miberas/0420`,
// a folder's README.md is the folder), so the codex's own relative links work as they are.
//
//   node build.mjs   writes dist/ (then `npx wrangler deploy` uploads it; see wrangler.jsonc)

import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import matter from 'gray-matter'
import { Marked } from 'marked'

const SITE = import.meta.dirname
const ROOT = path.resolve(SITE, '..')
const OUT = path.join(SITE, 'dist')
const REPO = 'https://github.com/mibera-rave/micodex'
const RAW = 'https://raw.githubusercontent.com/mibera-rave/micodex/main'
const SELF = 'https://codex.miberarave.xyz'
const HUB = 'https://miberarave.xyz'
const RING_KEY = 'codex' // this site's key in the hub's ring (lib/sites.ts there)
const AVOID = new Set([9136]) // never featured: its shirt is a political slogan (gumi's standing rule)

// ------------------------------------------------------------------ words (site/words.txt)

const WORDS = Object.fromEntries(
  fs
    .readFileSync(path.join(SITE, 'words.txt'), 'utf8')
    .split('\n')
    .filter((l) => l.trim() && !l.trimStart().startsWith('#'))
    .map((l) => [l.slice(0, l.indexOf('=')).trim(), l.slice(l.indexOf('=') + 1).trim()]),
)
function w(key, vars = {}) {
  if (!(key in WORDS)) throw new Error(`words.txt has no ${key}`)
  return esc(WORDS[key]).replace(/\{(\w+)\}/g, (_, k) => esc(String(vars[k] ?? '')))
}

// ------------------------------------------------------------------ which files become pages

const DIRS = [
  'miberas', 'miparcels', 'traits', 'core-lore', 'grails', 'birthdays', 'browse', 'fractures', 'mibera-sets',
  'vending-machine', 'special-collections', 'swag-scoring', 'oracle', 'identity', 'behind-the-scenes', 'agents',
  '_codex/data', '_codex/schema',
]
const ROOT_FILES = ['README.md', 'glossary.md', 'IDENTITY.md', 'SUMMARY.md', 'freeside-mibera-rave-archetype-mapping.md']

function walk(dir) {
  const out = []
  for (const e of fs.readdirSync(path.join(ROOT, dir), { withFileTypes: true })) {
    const rel = `${dir}/${e.name}`
    if (e.isDirectory()) out.push(...walk(rel))
    else if (e.name.endsWith('.md')) out.push(rel)
  }
  return out
}
const FILES = [...ROOT_FILES.filter((f) => fs.existsSync(path.join(ROOT, f))), ...DIRS.flatMap(walk)].sort()
const PAGES = new Set(FILES)

/** The address of a codex file's page. */
function urlOf(rel) {
  if (rel === 'README.md') return '/codex'
  if (path.posix.basename(rel) === 'README.md') return `/${path.posix.dirname(rel)}/`
  return `/${rel.replace(/\.md$/, '')}`
}
const fileOf = (url) => path.join(OUT, url.endsWith('/') ? `${url}index.html` : `${url}.html`)

// ------------------------------------------------------------------ links between pages

/** A link in `fromRel`'s markdown, as the site's address (or GitHub's, for files that aren't pages). */
function resolveHref(href, fromRel, image = false) {
  if (!href || href.startsWith('#') || /^[a-z][a-z0-9+.-]*:/i.test(href) || href.startsWith('//')) return href
  const at = href.indexOf('#')
  const hash = at === -1 ? '' : href.slice(at)
  let p = at === -1 ? href : href.slice(0, at)
  try { p = decodeURI(p) } catch {}
  let target = p.startsWith('/') ? p.slice(1) : path.posix.join(path.posix.dirname(fromRel), p)
  target = path.posix.normalize(target).replace(/\/$/, '')
  if (target.startsWith('..')) return href
  if (image) return `${RAW}/${encodeURI(target)}`
  if (PAGES.has(target)) return urlOf(target) + hash
  if (PAGES.has(`${target}/README.md`)) return urlOf(`${target}/README.md`) + hash
  if (target === '' || target === '.') return '/'
  const abs = path.join(ROOT, target)
  const kind = fs.existsSync(abs) && fs.statSync(abs).isDirectory() ? 'tree' : 'blob'
  return `${REPO}/${kind}/main/${encodeURI(target)}${hash}`
}

// ------------------------------------------------------------------ markdown

/** GitHub's heading anchors (github-slugger), so the codex's `file.md#anchor` links land. */
function slugger() {
  const seen = new Map()
  return (text) => {
    const base = text.toLowerCase().replace(/[^\p{L}\p{M}\p{N}\p{Pc}\- ]/gu, '').replace(/ /g, '-')
    let slug = base
    while (seen.has(slug)) {
      seen.set(base, seen.get(base) + 1)
      slug = `${base}-${seen.get(base)}`
    }
    seen.set(slug, 0)
    return slug
  }
}
const plain = (html) =>
  html.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'")

const ctx = { rel: '', src: '', slug: slugger(), toc: [] }
const md = new Marked({ gfm: true })
md.use({
  renderer: {
    heading({ tokens, depth }) {
      const inner = this.parser.parseInline(tokens)
      const id = ctx.slug(plain(inner).trim())
      if (depth === 2 || depth === 3) ctx.toc.push({ depth, id, text: plain(inner).trim() })
      const edit = depth === 2 ? `<span class="editsection">[<a href="${ctx.src}">${w('section.source')}</a>]</span>` : ''
      return `<h${depth} id="${esc(id)}">${edit}${inner}</h${depth}>\n`
    },
    link({ href, title, tokens }) {
      const to = resolveHref(href, ctx.rel)
      const ext = /^https?:/.test(to) && !to.startsWith(SELF)
      return `<a href="${esc(to)}"${title ? ` title="${esc(title)}"` : ''}${ext ? ' class="external"' : ''}>${this.parser.parseInline(tokens)}</a>`
    },
    image({ href, title, text }) {
      return `<img src="${esc(resolveHref(href, ctx.rel, true))}" alt="${esc(text)}"${title ? ` title="${esc(title)}"` : ''} loading="lazy">`
    },
  },
})

function startPage(rel) {
  ctx.rel = rel
  ctx.src = `${REPO}/blob/main/${encodeURI(rel)}`
  ctx.slug = slugger()
  ctx.toc = []
}
const inline = (text) => md.parseInline(String(text))

/** MediaWiki's contents box: before the first section, once a page has four or more. */
function withToc(html) {
  if (ctx.toc.length < 4) return html
  let list = '<ol>'
  let open = false
  for (const h of ctx.toc) {
    if (h.depth === 3 && !open) { list = list.replace(/<\/li>$/, ''); list += '<ol>'; open = true }
    else if (h.depth === 2 && open) { list += '</ol></li>'; open = false }
    list += `<li><a href="#${esc(h.id)}">${esc(h.text)}</a></li>`
  }
  list += open ? '</ol></li></ol>' : '</ol>'
  const toc = `<div id="toc"><div class="toctitle">${w('toc.title')}</div>${list}</div>\n`
  const first = html.search(/<h2[ >]/)
  return first === -1 ? html + toc : html.slice(0, first) + toc + html.slice(first)
}

// ------------------------------------------------------------------ dates, from git

const SHA = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: ROOT }).toString().trim()
const MODIFIED = new Map()
{
  const log = execFileSync('git', ['log', '--format=%x01%ct', '--name-only', '--no-renames'], { cwd: ROOT, maxBuffer: 1 << 30 }).toString()
  let time = 0
  for (const line of log.split('\n')) {
    if (line.startsWith('\x01')) time = Number(line.slice(1))
    else if (line && !MODIFIED.has(line)) MODIFIED.set(line, time)
  }
}
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
function modified(rel) {
  const d = new Date((MODIFIED.get(rel) ?? Math.floor(Date.now() / 1000)) * 1000)
  const two = (n) => String(n).padStart(2, '0')
  return { time: `${two(d.getUTCHours())}:${two(d.getUTCMinutes())}`, date: `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}` }
}

// ------------------------------------------------------------------ the page around the content

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

const ringBar = `<table class="ring"><tr>
<td><a class="btn" href="${HUB}/ring">${w('ring.button')}</a></td>
<td><b>${w('ring.name')}</b><br>[ <a href="${HUB}/ring/prev?from=${RING_KEY}">${w('ring.previous')}</a> | <a href="${HUB}/ring/next?from=${RING_KEY}">${w('ring.next')}</a> | <a href="${HUB}/ring/random?from=${RING_KEY}">${w('ring.random')}</a> | <a href="${HUB}/ring">${w('ring.list')}</a> ]</td>
</tr></table>`

const NAV = [
  ['nav.main', '/'],
  ['nav.tribes', '/core-lore/archetypes'],
  ['nav.ancestors', '/core-lore/ancestors/'],
  ['nav.drugs', '/core-lore/drug-tarot-system'],
  ['nav.grails', '/grails/'],
  ['nav.birthdays', '/birthdays/'],
  ['nav.agents', '/agents/'],
  ['nav.random', '/special/random'],
]

function shell({ title, rel = null, body, sub = true, backlinks = null, heading = true, tab = 'tab.article' }) {
  const src = rel ? `${REPO}/blob/main/${encodeURI(rel)}` : REPO
  const history = rel ? `${REPO}/commits/main/${encodeURI(rel)}` : `${REPO}/commits/main`
  const discussion = `${REPO}/issues?q=${encodeURIComponent(`"${title}"`)}`
  const tools = [
    backlinks ? `<li><a href="#${esc(backlinks)}">${w('tool.links')}</a></li>` : '',
    `<li><a href="javascript:print()">${w('tool.print')}</a></li>`,
    rel ? `<li><a href="${REPO}/blob/${SHA}/${encodeURI(rel)}">${w('tool.permanent')}</a></li>` : '',
    rel ? `<li><a href="${RAW}/${encodeURI(rel)}">${w('tool.raw')}</a></li>` : '',
  ].join('')
  const when = modified(rel)
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${esc(title)} - ${w('site.name')}</title>
<link rel="icon" href="/favicon.ico">
<link rel="stylesheet" href="/monobook.css">
${rel ? `<link rel="alternate" type="text/markdown" href="${RAW}/${encodeURI(rel)}">` : ''}
<script src="/site.js" defer></script>
</head>
<body>
<div id="wrap">
<div id="logo"><a href="/" title="${w('nav.main')}"><img src="/smiley.png" alt="${w('site.name')}"></a></div>
<ul id="tabs">
<li class="selected"><a href="">${w(tab)}</a></li>
<li><a href="${discussion}">${w('tab.discussion')}</a></li>
<li><a href="${src}">${w('tab.source')}</a></li>
<li><a href="${history}">${w('tab.history')}</a></li>
</ul>
<div id="side">
<div class="portlet"><h5>${w('side.navigation')}</h5><div class="pBody"><ul>${NAV.map(([k, u]) => `<li><a href="${u}">${w(k)}</a></li>`).join('')}</ul></div></div>
<div class="portlet"><h5>${w('side.search')}</h5><div class="pBody"><form id="searchform" action="/special/search"><input type="text" name="q" accesskey="f"> <button name="go">${w('search.go')}</button> <button name="fulltext">${w('search.search')}</button></form></div></div>
<div class="portlet"><h5>${w('side.toolbox')}</h5><div class="pBody"><ul>${tools}</ul></div></div>
</div>
<div id="content">
${heading ? `<h1 class="firstHeading">${esc(title)}</h1>` : ''}
${sub ? `<div id="siteSub">${w('site.sub')}</div>` : ''}
<div id="bodyContent">
${body}
</div>
</div>
<div id="footer"><span class="badge">${w('footer.powered').replace(' MediaWiki', '<br><b>MediaWiki</b>')}</span><ul><li>${w('footer.modified', when)}</li><li>${w('footer.license')}</li></ul></div>
${ringBar}
</div>
</body>
</html>
`
}

function write(url, html) {
  const file = fileOf(url)
  fs.mkdirSync(path.dirname(file), { recursive: true })
  fs.writeFileSync(file, html)
}

// ------------------------------------------------------------------ infoboxes

const label = (key) => key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
function value(v) {
  if (v instanceof Date) return v.toISOString().slice(0, 10)
  if (Array.isArray(v)) return v.filter((x) => typeof x !== 'object').join(', ')
  return String(v)
}
const SKIP = new Set(['image', 'ipfs_image', 'id', 'type', 'name', 'title'])

function infobox(title, fm, picture) {
  const rows = Object.entries(fm)
    .filter(([k, v]) => !SKIP.has(k) && v !== null && v !== undefined && (typeof v !== 'object' || v instanceof Date || Array.isArray(v)))
    .filter(([, v]) => value(v) !== '' && value(v).length <= 140)
    .map(([k, v]) => {
      const s = value(v)
      return `<tr><th>${esc(label(k))}</th><td>${/^https?:\/\//.test(s) ? `<a class="external" href="${esc(s)}">${esc(s)}</a>` : esc(s)}</td></tr>`
    })
  if (!rows.length && !picture) return ''
  return `<table class="infobox"><tr><th class="head" colspan="2">${esc(title)}</th></tr>${picture ? `<tr><td class="pic" colspan="2"><img src="${esc(picture)}" alt="${esc(title)}"></td></tr>` : ''}${rows.join('')}</table>\n`
}

// ------------------------------------------------------------------ a page from a codex file

const isImageOnly = (t, url) =>
  t.type === 'paragraph' && t.tokens.filter((x) => !(x.type === 'text' && !x.text.trim())).every((x) => x.type === 'image' && (!url || x.href === url)) && t.tokens.some((x) => x.type === 'image')

function readFile(rel) {
  const { data: fm, content } = matter(fs.readFileSync(path.join(ROOT, rel), 'utf8'))
  const tokens = md.lexer(content)
  const h1 = tokens.findIndex((t) => t.type === 'heading' && t.depth === 1)
  let title = fm.name || fm.title || (h1 !== -1 ? plain(md.parseInline(tokens[h1].text)) : null) || path.posix.basename(rel, '.md')
  if (path.posix.basename(rel) === 'README.md' && h1 === -1 && !fm.name) title = path.posix.basename(path.posix.dirname(rel)) || 'Codex'
  if (h1 !== -1) tokens.splice(h1, 1)
  return { fm, tokens, title: String(title) }
}

function renderTokens(tokens) {
  return withToc(md.parser(tokens))
}

const backlinksOf = (html) => html.match(/@generated:backlinks-start -->\s*<h\d id="([^"]+)"/)?.[1] ?? null

function genericPage(rel) {
  startPage(rel)
  const { fm, tokens, title } = readFile(rel)
  let picture = typeof fm.image === 'string' && /^https?:/.test(fm.image) ? fm.image : null
  if (picture) {
    // the picture moves into the infobox: drop its first copy in the body
    const at = tokens.findIndex((t) => (t.type === 'html' && t.raw.includes(picture)) || isImageOnly(t, picture))
    if (at !== -1) tokens.splice(at, 1)
  }
  const box = infobox(title, fm, picture)
  const html = renderTokens(tokens)
  return { title, html: shell({ title, rel, body: box + html, backlinks: backlinksOf(html) }) }
}

// A Mibera: the mockup's layout. Its picture and identity in the infobox, the reveal timeline as a gallery, the
// visual traits as a table, then See also. Everything comes from its file; anything else in it follows as written.
const IDENTITY_ROWS = ['Archetype', 'Ancestor', 'Birthday', 'Time Period', 'Sun Sign', 'Moon Sign', 'Ascending Sign', 'Element', 'Drug', 'Swag Rank', 'Swag Score', 'Parcel']
const VISUAL_ROWS = ['Background', 'Body', 'Hair', 'Eyes', 'Eyebrows', 'Mouth', 'Shirt', 'Hat', 'Glasses', 'Mask', 'Earrings', 'Face Accessory', 'Tattoo', 'Item']
const SEE_ALSO = ['Archetype', 'Ancestor', 'Drug', 'Birthday', 'Parcel']

function miberaPage(rel) {
  startPage(rel)
  const { fm, tokens, title } = readFile(rel)
  if (fm.grail || !fm.archetype) return genericPage(rel) // the 44 grails placed on a Mibera: their own short page
  const take = (i) => (i === -1 ? null : tokens.splice(i, 1)[0])
  const headingAt = (text) => tokens.findIndex((t) => t.type === 'heading' && t.text.trim().toLowerCase() === text)

  const pic = take(tokens.findIndex((t) => isImageOnly(t)))
  const picture = pic?.tokens.find((x) => x.type === 'image')?.href ?? null

  let gallery = ''
  const tl = headingAt('reveal timeline')
  if (tl !== -1) {
    take(tl)
    const table = take(tokens.findIndex((t, i) => i >= tl && t.type === 'table'))
    if (table) {
      gallery = table.header
        .map((h, i) => {
          const img = table.rows[0]?.[i]?.tokens.find((x) => x.type === 'image')
          return img ? `<span><img src="${esc(img.href)}" alt="" loading="lazy">${esc(h.text)}</span>` : ''
        })
        .join('')
    }
  }

  const traits = new Map()
  const tr = headingAt('traits')
  if (tr !== -1) {
    take(tr)
    const table = take(tokens.findIndex((t, i) => i >= tr && t.type === 'table'))
    for (const row of table?.rows ?? []) traits.set(row[0].text.trim(), row[1].text.trim())
  }
  // the closing "Back to Index" line and its rule
  for (let i = tokens.length - 1; i >= 0; i--) {
    const t = tokens[i]
    if ((t.type === 'paragraph' && /Back to Index/.test(t.text)) || t.type === 'hr' || t.type === 'space') tokens.splice(i, 1)
    else break
  }

  const cell = (k) => inline(traits.get(k))
  const box = `<table class="infobox"><tr><th class="head" colspan="2">${esc(title)}</th></tr>${picture ? `<tr><td class="pic" colspan="2"><img src="${esc(picture)}" alt="${esc(title)}"></td></tr>` : ''}${IDENTITY_ROWS.filter((k) => traits.has(k)).map((k) => `<tr><th>${esc(k)}</th><td>${cell(k)}</td></tr>`).join('')}</table>\n`

  ctx.toc = []
  const sections = []
  const section = (name, html) => {
    const id = ctx.slug(name)
    ctx.toc.push({ depth: 2, id, text: name })
    sections.push(`<h2 id="${esc(id)}"><span class="editsection">[<a href="${ctx.src}">${w('section.source')}</a>]</span>${esc(name)}</h2>\n${html}`)
  }
  if (gallery) section(plain(w('mibera.timeline')), `<div class="gallery">${gallery}</div>`)
  const visual = VISUAL_ROWS.filter((k) => traits.has(k) && !/^none$/i.test(traits.get(k)))
  if (visual.length) {
    section(plain(w('mibera.traits')), `<table class="wikitable"><tr><th>${w('mibera.trait')}</th><th>${w('mibera.value')}</th></tr>${visual.map((k) => `<tr><td>${esc(k)}</td><td>${cell(k)}</td></tr>`).join('')}</table>`)
  }
  const rest = md.parser(tokens)
  if (rest.trim()) sections.push(rest)
  const also = SEE_ALSO.filter((k) => traits.has(k)).map((k) => `<li>${cell(k)}</li>`)
  if (also.length) section(plain(w('mibera.seealso')), `<ul>${also.join('')}</ul>`)
  const body = box + sections.join('\n')
  return { title, html: shell({ title, rel, body: withToc(body), backlinks: backlinksOf(rest) }) }
}

// ------------------------------------------------------------------ build

fs.rmSync(OUT, { recursive: true, force: true })
fs.mkdirSync(OUT, { recursive: true })
const index = []
const started = Date.now()

for (const rel of FILES) {
  const isMibera = /^miberas\/\d+\.md$/.test(rel)
  let page
  try {
    page = isMibera ? miberaPage(rel) : genericPage(rel)
  } catch (e) {
    throw new Error(`${rel}: ${e.stack}`)
  }
  write(urlOf(rel), page.html)
  index.push([page.title, urlOf(rel)])
}

// The contracts page, from _codex/data/contracts.json.
{
  const data = JSON.parse(fs.readFileSync(path.join(ROOT, '_codex/data/contracts.json'), 'utf8'))
  const rel = '_codex/data/contracts.json'
  startPage(rel)
  const title = plain(w('contracts.title'))
  const rows = data.contracts
    .map((c) => `<tr><td>${esc(c.name)}</td><td><code>${esc(c.address)}</code></td><td>${esc(c.chain)} (${esc(c.chain_id)})</td><td>${esc(c.standard ?? '')}</td><td>${inline(c.notes ?? '')}</td></tr>`)
    .join('')
  const body = `${data.note ? `<p>${inline(data.note)}</p>` : ''}<table class="wikitable"><tr><th>Name</th><th>Address</th><th>Chain</th><th>Standard</th><th>Notes</th></tr>${rows}</table>`
  write('/_codex/data/contracts', shell({ title, rel, body }))
  index.push([title, '/_codex/data/contracts'])
}

// The main page.
{
  startPage('README.md')
  const count = (dir) => FILES.filter((f) => f.startsWith(`${dir}/`) && /\/\d+\.md$/.test(f)).length
  let traitCount = FILES.filter((f) => f.startsWith('traits/') && !/README\.md$|overview\.md$/.test(f)).length
  try { traitCount = JSON.parse(fs.readFileSync(path.join(ROOT, 'manifest.json'), 'utf8')).entity_types?.trait?.count ?? traitCount } catch {}
  const grails = FILES.filter((f) => /^grails\/(?!README)[^/]+\.md$/.test(f)).length

  // The codex's own map of itself: README's "The Codex Structure", as written.
  const readme = fs.readFileSync(path.join(ROOT, 'README.md'), 'utf8')
  const structure = readme.match(/\n## The Codex Structure\n([\s\S]*?)\n## /)?.[1] ?? ''
  const codexBox = md.parser(md.lexer(structure.replace(/^### /gm, '#### ').replace(/^---$/gm, '')))

  // Featured Mibera: a different one each day the site is built.
  const day = Math.floor(Date.now() / 86400000)
  let featured = ''
  for (let k = 0; k < 10000 && !featured; k++) {
    const id = ((day * 7919 + k) % 10000) + 1
    if (AVOID.has(id)) continue
    const rel = `miberas/${String(id).padStart(4, '0')}.md`
    if (!PAGES.has(rel)) continue
    const { data: fm, content } = matter(fs.readFileSync(path.join(ROOT, rel), 'utf8'))
    if (fm.grail || !fm.archetype) continue
    const pic = content.match(/!\[[^\]]*\]\((https?:[^)]+)\)/)?.[1]
    startPage(rel)
    const facts = ['archetype', 'ancestor', 'drug', 'element']
      .filter((k) => fm[k])
      .map((k) => `${esc(label(k))}: <b>${esc(fm[k])}</b>`)
      .join('<br>')
    featured = `${pic ? `<a href="${urlOf(rel)}"><img src="${esc(pic)}" alt="Mibera #${id}"></a>` : ''}<p><b><a href="${urlOf(rel)}">Mibera #${id}</a></b></p><p>${facts}</p><p><a href="${urlOf(rel)}">${w('main.featured.more', { id })}</a></p><div style="clear:both"></div>`
  }
  startPage('README.md')

  const browse = FILES.filter((f) => /^browse\/(?!README)[^/]+\.md$/.test(f))
    .map((f) => `<li><a href="${urlOf(f)}">${esc(readFile(f).title)}</a></li>`)
    .join('')

  const total = index.length + 1
  const body = `<div class="mp-welcome"><div class="big">${w('main.welcome')}</div><div>${w('main.welcome2')}</div><div class="small">${w('main.count', { pages: total.toLocaleString('en-US'), miberas: count('miberas').toLocaleString('en-US'), parcels: count('miparcels').toLocaleString('en-US'), traits: Number(traitCount).toLocaleString('en-US'), grails })}</div></div>
<div class="mp-cols">
<div class="mp-col"><div class="mp-box mp-a"><h2>${w('main.codex')}</h2><div class="in">${codexBox}</div></div></div>
<div class="mp-col">
<div class="mp-box mp-b mp-featured"><h2>${w('main.featured')}</h2><div class="in">${featured}</div></div>
<div class="mp-box mp-c"><h2>${w('main.agents')}</h2><div class="in"><p>${w('main.agents.text')}</p><p><a href="/agents/">${w('main.agents.link')}</a></p></div></div>
<div class="mp-box mp-d"><h2>${w('main.browse')}</h2><div class="in"><ul>${browse}</ul></div></div>
</div>
</div>`
  write('/', shell({ title: plain(w('main.title')), rel: 'README.md', body, sub: false, heading: false }))
  index.unshift([plain(w('main.title')), '/'])
}

// Search, Random Mibera, and the page for an address that isn't there.
{
  startPage('')
  const q = { q: '@@Q@@' }
  const slot = '<span class="searchq"></span>'
  write('/special/search', shell({ title: plain(w('special.search')), body: `<p id="searchnone" hidden>${w('special.search.none', q).replace('@@Q@@', slot)}</p><div id="searchsome" hidden><p>${w('special.search.matches', q).replace('@@Q@@', slot)}</p><ul id="searchresults"></ul></div>` }))
  // An image's own page: whichever picture was clicked, large, with its full-size file and the page it came from.
  // site.js fills it in from the address (?src=, ?title=, ?from=).
  write('/special/image', shell({ title: plain(w('image.title')), tab: 'image.tab', sub: false, body: `<div id="imagepage" data-prefix="${w('image.title')}"><p><a id="imagefull"><img id="imagefile" alt=""></a></p><p><a id="imagefulltext">${w('image.full')}</a> <span id="imagesize" data-words="${w('image.size', { w: '@@W@@', h: '@@H@@' })}"></span></p><h2>${w('image.links')}</h2><p>${w('image.linkstext')}</p><ul><li><a id="imagefrom"></a></li></ul></div>` }))
  write('/special/random', shell({ title: plain(w('special.random')), body: `<p id="randommibera"><a href="/miberas/0001">Mibera #1</a></p>` }))
  fs.writeFileSync(path.join(OUT, '404.html'), shell({ title: plain(w('missing.title')), body: `<p>${w('missing.text')}</p><p><a href="/">${w('missing.back')}</a></p>` }))
}

// For agents and search: the title index, the codex's llms files and its skill file.
fs.writeFileSync(path.join(OUT, 'search.json'), JSON.stringify(index))
for (const f of fs.readdirSync(path.join(SITE, 'static'))) fs.copyFileSync(path.join(SITE, 'static', f), path.join(OUT, f))
for (const f of ['llms.txt', 'llms-full.txt']) if (fs.existsSync(path.join(ROOT, f))) fs.copyFileSync(path.join(ROOT, f), path.join(OUT, f))

// The old docs site's addresses, so links to them keep working.
fs.writeFileSync(
  path.join(OUT, '_redirects'),
  [
    ['/for-agents', '/agents/'],
    ['/story/philosophy', '/core-lore/philosophy'],
    ['/story/official-lore', '/core-lore/official-lore'],
    ['/framework/ancestors', '/core-lore/ancestors/'],
    ['/tools/lookup_mibera', '/miberas/'],
    ['/tools/lookup_grail', '/grails/'],
    ['/tools/lookup_archetype', '/core-lore/archetypes'],
    ['/tools/list_archetypes', '/core-lore/archetypes'],
    ['/tools/lookup_zone', '/core-lore/festival-zones-vocabulary'],
    ['/tools/list_zones', '/core-lore/festival-zones-vocabulary'],
    ['/tools/lookup_factor', '/core-lore/factor-lore'],
    ['/tools/validate_world_element', '/agents/'],
    ['/on-chain', '/_codex/data/contracts'],
    ['/data', '/_codex/data/'],
    ['/coverage-gaps', '/agents/'],
    ['/discovery', '/agents/'],
  ]
    .flatMap(([from, to]) => [`${from} ${to} 301`, ...(from.endsWith('/') ? [] : [`${from}/ ${to} 301`])])
    .join('\n') + '\n',
)

const files = (dir) => fs.readdirSync(dir, { withFileTypes: true }).reduce((n, e) => n + (e.isDirectory() ? files(path.join(dir, e.name)) : 1), 0)
console.log(`MiCodex: ${index.length} pages, ${files(OUT)} files in dist/, ${((Date.now() - started) / 1000).toFixed(1)} s`)
