/**
 * FE Maker's ticket relay (Cloudflare Worker `fe-maker-tickets`, CAHIER_DES_CHARGES.md section 4, alpha step 7).
 *
 * Testers send their tickets without a GitHub account: FE Maker posts them here, the Worker keeps the token (secret
 * GITHUB_TOKEN) and writes them as issues of the private feedback repository (FEEDBACK_REPO), screenshots and the
 * optional project in its uploads/ folder. Each ticket gets a secret code: only its sender reads it back (status,
 * replies) and answers it. The admin reads everything on GitHub (or in FE Maker, with their own token).
 *
 *   POST /v1/tickets                     {kind, priority, body, context, version, images: [dataURL], project?}
 *                                        -> {number, secret}
 *   GET  /v1/tickets/:number             header X-Ticket-Secret -> {number, state, comments}
 *   POST /v1/tickets/:number/comments    header X-Ticket-Secret, {body, images} -> {ok}
 */

const API = 'https://api.github.com'
const KINDS = ['bug', 'idea', 'question']
const PRIORITIES = ['high', 'normal', 'low']
const MAX_BODY = 20000            // characters of text
const MAX_IMAGES = 4
const MAX_IMAGE = 3 * 1024 * 1024 // bytes, decoded
const MAX_PROJECT = 10 * 1024 * 1024
const MAX_REQUEST = 25 * 1024 * 1024
const RATE = { posts: 10, seconds: 600 } // per address: tickets and replies
const IMAGE_TYPES = { 'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif' }
const SECRET_MARK = /<!-- fem:secret=([0-9a-f]{64}) -->\s*$/
const TESTER_MARK = '<!-- fem:tester -->'

export default {
  async fetch(request, env, ctx) {
    try {
      return await route(request, env, ctx)
    } catch (e) {
      if (e instanceof Refusal) return json({ error: e.code }, e.status)
      return json({ error: 'relayError' }, 502)
    }
  },
}

class Refusal extends Error {
  constructor(code, status = 400) {
    super(code)
    this.code = code
    this.status = status
  }
}

async function route(request, env, ctx) {
  const url = new URL(request.url)
  const parts = url.pathname.split('/').filter(Boolean)
  if (parts[0] !== 'v1' || parts[1] !== 'tickets') throw new Refusal('notFound', 404)
  if (parts.length === 2 && request.method === 'POST') {
    await limit(request, env, ctx)
    return json(await createTicket(await readJson(request), env))
  }
  const number = Number(parts[2])
  if (!Number.isInteger(number) || number <= 0) throw new Refusal('notFound', 404)
  const secret = request.headers.get('X-Ticket-Secret') || ''
  if (parts.length === 3 && request.method === 'GET') return json(await readTicket(number, secret, env))
  if (parts.length === 4 && parts[3] === 'comments' && request.method === 'POST') {
    await limit(request, env, ctx)
    return json(await addComment(number, secret, await readJson(request), env))
  }
  throw new Refusal('notFound', 404)
}

async function readJson(request) {
  const size = Number(request.headers.get('Content-Length') || 0)
  if (size > MAX_REQUEST) throw new Refusal('tooBig', 413)
  const text = await request.text()
  if (text.length > MAX_REQUEST) throw new Refusal('tooBig', 413)
  try {
    return JSON.parse(text)
  } catch {
    throw new Refusal('badRequest')
  }
}

/** Posts per address and time window, kept in the data center's cache (enough against a flood). */
async function limit(request, env, ctx) {
  const address = request.headers.get('CF-Connecting-IP') || 'unknown'
  const cache = env.CACHE ?? (typeof caches !== 'undefined' ? caches.default : null)
  if (!cache) return
  const window = Math.floor(Date.now() / 1000 / RATE.seconds)
  const key = new Request(`https://rate.fe-maker/${encodeURIComponent(address)}/${window}`)
  const hit = await cache.match(key)
  const count = hit ? Number(await hit.text()) : 0
  if (count >= RATE.posts) throw new Refusal('tooMany', 429)
  const put = cache.put(key, new Response(String(count + 1), { headers: { 'Cache-Control': `max-age=${RATE.seconds}` } }))
  if (ctx?.waitUntil) ctx.waitUntil(put)
  else await put
}

/** Tester text in Markdown: no HTML comment (the relay's marks), no mention that would notify someone. */
export function clean(text, max = MAX_BODY) {
  return String(text ?? '').slice(0, max).replace(/<!--/g, '&lt;!--').replace(/@(\w)/g, '@​$1')
}

async function sha256(text) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

function randomHex(bytes) {
  return [...crypto.getRandomValues(new Uint8Array(bytes))].map((b) => b.toString(16).padStart(2, '0')).join('')
}

function decodeBase64(data, max, code) {
  if (typeof data !== 'string' || !/^[A-Za-z0-9+/=\s]*$/.test(data)) throw new Refusal(code)
  const size = Math.floor((data.replace(/\s|=/g, '').length * 3) / 4)
  if (size > max) throw new Refusal(code === 'badImage' ? 'imageTooBig' : 'projectTooBig', 413)
  return data.replace(/\s/g, '')
}

async function github(env, method, path, body) {
  const response = await fetch(`${API}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: 'application/vnd.github+json',
      'User-Agent': 'fe-maker-tickets',
      'X-GitHub-Api-Version': '2022-11-28',
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (response.status === 404) throw new Refusal('notFound', 404)
  if (!response.ok) throw new Error(`GitHub ${method} ${path}: ${response.status}`)
  return response.status === 204 ? null : response.json()
}

/** Screenshots (and the project) into the repository's uploads/ folder: links that only its readers can open. */
async function upload(env, name, base64, message) {
  const path = `uploads/${new Date().toISOString().slice(0, 7)}/${name}`
  await github(env, 'PUT', `/repos/${env.FEEDBACK_REPO}/contents/${path}`, { message, content: base64 })
  return `https://github.com/${env.FEEDBACK_REPO}/blob/main/${path}?raw=true`
}

async function uploadImages(env, images, prefix) {
  if (!Array.isArray(images ?? [])) throw new Refusal('badImage')
  if ((images ?? []).length > MAX_IMAGES) throw new Refusal('tooManyImages')
  const decoded = (images ?? []).map((dataUrl) => {
    const m = /^data:(image\/[\w+.-]+);base64,(.+)$/s.exec(String(dataUrl))
    if (!m || !IMAGE_TYPES[m[1]]) throw new Refusal('badImage')
    return { ext: IMAGE_TYPES[m[1]], data: decodeBase64(m[2], MAX_IMAGE, 'badImage') }
  })
  const links = []
  for (const [i, image] of decoded.entries())
    links.push(await upload(env, `${prefix}-${i + 1}.${image.ext}`, image.data, `Screenshot ${prefix}-${i + 1}`))
  return links
}

function contextLines(context) {
  const lines = []
  for (const [key, value] of Object.entries(context && typeof context === 'object' ? context : {}).slice(0, 12)) {
    if (value === null || value === undefined || value === '' || typeof value === 'object') continue
    lines.push(`| ${clean(key, 40).replace(/\|/g, '/')} | ${clean(value, 200).replace(/\|/g, '/').replace(/\n/g, ' ')} |`)
  }
  return lines.length ? ['', '| | |', '|---|---|', ...lines] : []
}

export async function createTicket(input, env) {
  const body = clean(input.body).trim()
  if (!body) throw new Refusal('bodyEmpty')
  const kind = KINDS.includes(input.kind) ? input.kind : 'bug'
  const priority = PRIORITIES.includes(input.priority) ? input.priority : 'normal'
  const version = clean(input.version, 40).replace(/[^\w.+-]/g, '')
  const key = randomHex(4)
  const images = await uploadImages(env, input.images, key)
  let project = ''
  if (input.project) {
    const data = decodeBase64(input.project.data, MAX_PROJECT, 'badProject')
    project = await upload(env, `${key}-project.zip`, data, `Project ${key}`)
  }
  const secret = randomHex(16)
  const first = body.split('\n')[0].slice(0, 70)
  const text = [
    body,
    ...contextLines({ ...(input.context ?? {}), version }),
    ...images.map((link, i) => `\n![Capture ${i + 1}](${link})`),
    ...(project ? [`\n[Projet joint](${project})`] : []),
    '',
    `<!-- fem:secret=${await sha256(secret)} -->`,
  ].join('\n')
  const issue = await github(env, 'POST', `/repos/${env.FEEDBACK_REPO}/issues`, {
    title: `[${kind}] ${first}`,
    body: text,
    labels: [kind, `priority:${priority}`, ...(version ? [`v${version}`] : [])],
  })
  return { number: issue.number, secret }
}

async function checkedIssue(number, secret, env) {
  if (!/^[0-9a-f]{32}$/.test(secret)) throw new Refusal('notFound', 404)
  const issue = await github(env, 'GET', `/repos/${env.FEEDBACK_REPO}/issues/${number}`)
  const mark = SECRET_MARK.exec(issue.body ?? '')
  if (!mark || mark[1] !== (await sha256(secret)) || issue.pull_request) throw new Refusal('notFound', 404)
  return issue
}

export async function readTicket(number, secret, env) {
  const issue = await checkedIssue(number, secret, env)
  const comments = await github(env, 'GET', `/repos/${env.FEEDBACK_REPO}/issues/${number}/comments?per_page=100`)
  return {
    number,
    state: issue.state === 'closed' ? (issue.state_reason === 'not_planned' ? 'cancelled' : 'done') : 'open',
    comments: comments.map((c) => ({
      from: (c.body ?? '').includes(TESTER_MARK) ? 'tester' : 'admin',
      body: (c.body ?? '').replace(TESTER_MARK, '').trim(),
      createdAt: c.created_at,
    })),
  }
}

export async function addComment(number, secret, input, env) {
  await checkedIssue(number, secret, env)
  const body = clean(input.body).trim()
  if (!body) throw new Refusal('bodyEmpty')
  const images = await uploadImages(env, input.images, `${number}-${randomHex(3)}`)
  await github(env, 'POST', `/repos/${env.FEEDBACK_REPO}/issues/${number}/comments`, {
    body: [body, ...images.map((link, i) => `\n![Capture ${i + 1}](${link})`), '', TESTER_MARK].join('\n'),
  })
  return { ok: true }
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
}
