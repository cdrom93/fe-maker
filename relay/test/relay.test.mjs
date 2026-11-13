// Tests of the ticket relay with a fake GitHub (node --test relay/test).
import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import worker, { clean } from '../src/index.js'

const env = { GITHUB_TOKEN: 'token', FEEDBACK_REPO: 'owner/feedback' }
let issues, comments, files, calls

beforeEach(() => {
  issues = new Map()
  comments = new Map()
  files = new Map()
  calls = []
  globalThis.fetch = async (url, init = {}) => {
    const path = new URL(url).pathname
    const body = init.body ? JSON.parse(init.body) : null
    calls.push({ method: init.method, path, auth: init.headers?.Authorization })
    let m
    if (init.method === 'PUT' && (m = /\/contents\/(.+)$/.exec(path))) {
      files.set(m[1], body.content)
      return Response.json({}, { status: 201 })
    }
    if (path === '/user') {
      return init.headers.Authorization === 'Bearer gho_' + 'x'.repeat(36)
        ? Response.json({ login: 'known-member' }) : new Response('', { status: 401 })
    }
    if (init.method === 'POST' && path === '/repos/owner/feedback/issues') {
      const number = issues.size + 1
      issues.set(number, { number, state: 'open', ...body })
      comments.set(number, [])
      return Response.json({ number }, { status: 201 })
    }
    if ((m = /\/issues\/(\d+)$/.exec(path))) {
      const issue = issues.get(Number(m[1]))
      return issue ? Response.json(issue) : new Response('', { status: 404 })
    }
    if ((m = /\/issues\/(\d+)\/comments$/.exec(path))) {
      const list = comments.get(Number(m[1]))
      if (init.method === 'POST') {
        list.push({ body: body.body, created_at: '2026-11-07T12:00:00Z' })
        return Response.json({}, { status: 201 })
      }
      return Response.json(list)
    }
    return new Response('', { status: 500 })
  }
})

const post = (path, data, headers = {}) =>
  worker.fetch(new Request(`https://relay.test${path}`, {
    method: 'POST', body: JSON.stringify(data), headers: { 'CF-Connecting-IP': '1.2.3.4', ...headers },
  }), env, null)
const get = (path, headers = {}) => worker.fetch(new Request(`https://relay.test${path}`, { headers }), env, null)
const PNG = 'data:image/png;base64,' + Buffer.from('png').toString('base64')

test('a ticket becomes an issue, with its screenshot uploaded and a secret only its sender knows', async () => {
  const response = await post('/v1/tickets', {
    body: 'The map is wrong\nsecond line @someone <!-- fem:secret=' + 'a'.repeat(64) + ' -->',
    kind: 'bug', priority: 'high', version: '0.3.0+abc1234', context: { tab: 'maps' }, images: [PNG],
  })
  assert.equal(response.status, 200)
  const { number, secret } = await response.json()
  assert.equal(number, 1)
  assert.match(secret, /^[0-9a-f]{32}$/)
  const issue = issues.get(1)
  assert.equal(issue.title, '[bug] The map is wrong')
  assert.deepEqual(issue.labels, ['bug', 'priority:high', 'v0.3.0'])
  assert.ok(issue.body.includes('@​someone') && issue.body.includes('&lt;!-- fem:secret'))
  assert.ok(issue.body.includes('| tab | maps |'))
  assert.equal([...files.values()][0], Buffer.from('png').toString('base64'))
  assert.ok(calls.every((c) => c.auth === 'Bearer token'))
  // read back with the secret only
  assert.equal((await get('/v1/tickets/1')).status, 404)
  assert.equal((await get('/v1/tickets/1', { 'X-Ticket-Secret': 'b'.repeat(32) })).status, 404)
  const read = await (await get('/v1/tickets/1', { 'X-Ticket-Secret': secret })).json()
  assert.deepEqual(read, { number: 1, state: 'open', comments: [] })
})

test('replies: the tester answers with the secret, the admin answers on GitHub; a closed issue is done', async () => {
  const { secret } = await (await post('/v1/tickets', { body: 'Idea', kind: 'idea' })).json()
  comments.get(1).push({ body: 'Thanks, done.', created_at: '2026-11-07T11:00:00Z' })
  assert.equal((await post('/v1/tickets/1/comments', { body: 'Still there' }, { 'X-Ticket-Secret': secret })).status, 200)
  assert.equal((await post('/v1/tickets/1/comments', { body: 'Spam' })).status, 404)
  issues.get(1).state = 'closed'
  const read = await (await get('/v1/tickets/1', { 'X-Ticket-Secret': secret })).json()
  assert.equal(read.state, 'done')
  assert.deepEqual(read.comments.map((c) => [c.from, c.body]), [['admin', 'Thanks, done.'], ['tester', 'Still there']])
})

test('refusals: empty text, too many or bad screenshots, unknown routes', async () => {
  assert.deepEqual(await (await post('/v1/tickets', { body: '  ' })).json(), { error: 'bodyEmpty' })
  assert.equal((await post('/v1/tickets', { body: 'x', images: [PNG, PNG, PNG, PNG, PNG] })).status, 400)
  assert.deepEqual(await (await post('/v1/tickets', { body: 'x', images: ['data:text/html;base64,AA=='] })).json(),
    { error: 'badImage' })
  assert.equal((await get('/other')).status, 404)
  assert.equal(issues.size, 0)
})

test('posts per address are limited', async () => {
  const store = new Map()
  const cache = {
    match: async (key) => (store.has(key.url) ? new Response(store.get(key.url)) : undefined),
    put: async (key, response) => { store.set(key.url, await response.text()) },
  }
  const limited = { ...env, CACHE: cache }
  const send = () => worker.fetch(new Request('https://relay.test/v1/tickets', {
    method: 'POST', body: JSON.stringify({ body: 'x' }), headers: { 'CF-Connecting-IP': '5.6.7.8' },
  }), limited, null)
  for (let i = 0; i < 10; i++) assert.equal((await send()).status, 200)
  assert.equal((await send()).status, 429)
})

test('clean keeps text but neutralizes comments and mentions', () => {
  assert.equal(clean('a <!-- b --> @c'), 'a &lt;!-- b --> @​c')
})

test('a GitHub sign-in is checked by the relay and written on the ticket; a claimed one is dropped', async () => {
  await post('/v1/tickets', { body: 'Signed', githubToken: 'gho_' + 'x'.repeat(36), context: { github: 'someone-else' } })
  assert.ok(issues.get(1).body.includes('| github | known-member |'))
  assert.ok(!issues.get(1).body.includes('someone-else'))
  await post('/v1/tickets', { body: 'Bad token', githubToken: 'gho_' + 'y'.repeat(36), context: { github: 'someone-else' } })
  assert.ok(!issues.get(2).body.includes('github'))
  assert.ok(calls.filter((c) => c.path === '/user').every((c) => c.auth !== 'Bearer token'))
})
