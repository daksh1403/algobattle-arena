/**
 * api.test.ts — verifies AlgobattleClient wiring (URLs, headers, 401 handling).
 */

import * as assert from 'assert';
import { AlgobattleClient, ApiError } from '../../src/api/client';
import { FakeFetch, makeClient } from './_helpers';

suite('AlgobattleClient', () => {
  test('builds full URL and attaches Authorization header', async () => {
    const fake = new FakeFetch();
    fake.respondWith(200, { id: 'p1' });

    const client = makeClient((url, init) => fake.fetch(url, init), 'jwt-xyz');
    const data = await client.get<{ id: string }>('/problems/two-sum');
    assert.strictEqual(data.id, 'p1');
    assert.strictEqual(fake.calls.length, 1);

    const call = fake.calls[0]!;
    assert.ok(call.url.endsWith('/problems/two-sum'), `URL was ${call.url}`);
    const headers = (call.init?.headers ?? {}) as Record<string, string>;
    assert.strictEqual(headers['Authorization'], 'Bearer jwt-xyz');
    assert.strictEqual(headers['Accept'], 'application/json');
  });

  test('omits Authorization header when skipAuth=true', async () => {
    const fake = new FakeFetch();
    fake.respondWith(200, {});

    const client = makeClient((url, init) => fake.fetch(url, init), 'jwt-xyz');
    await client.post('/auth/login', new URLSearchParams({ username: 'a', password: 'b' }), {
      skipAuth: true,
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });

    const headers = (fake.calls[0]!.init?.headers ?? {}) as Record<string, string>;
    assert.strictEqual(headers['Authorization'], undefined);
    assert.strictEqual(headers['Content-Type'], 'application/x-www-form-urlencoded');
  });

  test('parses 401 JSON detail and surfaces ApiError', async () => {
    const fake = new FakeFetch();
    fake.respondWith(401, { detail: 'Token expired' });

    const client = makeClient((url, init) => fake.fetch(url, init), 'jwt-xyz');
    await assert.rejects(
      () => client.get('/users/me'),
      (err: unknown) => {
        if (!(err instanceof ApiError)) return false;
        assert.strictEqual(err.status, 401);
        assert.strictEqual(err.message, 'Token expired');
        return true;
      },
    );
  });

  test('falls back to statusText when error body is not JSON', async () => {
    const fake = new FakeFetch();
    fake.respondWith = () => new Response('not json', { status: 500, statusText: 'Internal Server Error' });

    const client = makeClient((url, init) => fake.fetch(url, init), 'jwt-xyz');
    await assert.rejects(
      () => client.get('/oops'),
      (err: unknown) => {
        if (!(err instanceof ApiError)) return false;
        assert.strictEqual(err.status, 500);
        assert.strictEqual(err.message, 'Internal Server Error');
        return true;
      },
    );
  });

  test('serializes object body as JSON with Content-Type', async () => {
    const fake = new FakeFetch();
    fake.respondWith(200, { ok: true });

    const client = makeClient((url, init) => fake.fetch(url, init), null);
    await client.post('/echo', { hello: 'world' });

    const call = fake.calls[0]!;
    const headers = (call.init?.headers ?? {}) as Record<string, string>;
    assert.strictEqual(headers['Content-Type'], 'application/json');
    assert.ok(typeof call.init?.body === 'string');
    assert.ok((call.init.body as string).includes('"hello":"world"'));
  });

  test('appends query string when query option is supplied', async () => {
    const fake = new FakeFetch();
    fake.respondWith(200, { items: [] });
    const client = makeClient((url, init) => fake.fetch(url, init), null);
    await client.get('/problems', { query: { difficulty: 'easy', page: 2, _: undefined } });
    const url = fake.calls[0]!.url;
    assert.ok(url.includes('difficulty=easy'), url);
    assert.ok(url.includes('page=2'), url);
    assert.ok(!url.includes('_='), url);
  });
});
