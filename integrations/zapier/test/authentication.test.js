'use strict';

const nock = require('nock');

const { App, appTester, API, KEY, bundle } = require('./helpers');

describe('authentication', () => {
  afterEach(() => nock.cleanAll());

  it('tests the key with GET /public/v1/me and labels the connection with the workspace', async () => {
    nock(API, { reqheaders: { authorization: `Bearer ${KEY}` } })
      .get('/public/v1/me')
      .reply(200, {
        workspace_id: 'w1',
        workspace_name: 'Maple Bakery',
        key_id: 'k1',
        scopes: ['contacts:read'],
      });
    const result = await appTester(App.authentication.test, bundle());
    expect(result.workspace_name).toBe('Maple Bakery');
    expect(App.authentication.connectionLabel).toBe('{{workspace_name}}');
  });

  it('says what to do when the key is refused', async () => {
    nock(API).get('/public/v1/me').reply(401, { code: 'unauthorized', detail: 'That API key isn’t valid.' });
    await expect(appTester(App.authentication.test, bundle())).rejects.toThrow(/Make a new key/);
  });

  it('asks for one secret field, the API key', () => {
    expect(App.authentication.fields.map((f) => [f.key, f.type, f.required])).toEqual([
      ['api_key', 'password', true],
    ]);
  });
});
