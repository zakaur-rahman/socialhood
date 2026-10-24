'use strict';

const nock = require('nock');

const { idempotencyKey, RETRY_WINDOW_MS } = require('../lib/idempotency');
const { App, appTester, API, KEY, bundle } = require('./helpers');

const auth = { reqheaders: { authorization: `Bearer ${KEY}` } };
const CONTACT = '5b1b3f1e-6a53-4b4e-8f0e-2d2b9a7c1a11';
const record = { id: CONTACT, name: 'Priya Shah', platform: 'instagram', username: 'priya.shah', tags: [] };

describe('actions', () => {
  afterEach(() => nock.cleanAll());

  it('add tag puts the tag in "add"', async () => {
    nock(API, auth)
      .post(`/public/v1/contacts/${CONTACT}/tags`, { add: ['t1'] })
      .reply(200, record);
    const result = await appTester(
      App.creates.add_tag.operation.perform,
      bundle({ inputData: { contact_id: CONTACT, tag_id: 't1' } }),
    );
    expect(result.id).toBe(CONTACT);
  });

  it('remove tag puts the tag in "remove"', async () => {
    nock(API, auth)
      .post(`/public/v1/contacts/${CONTACT}/tags`, { remove: ['t1'] })
      .reply(200, record);
    await appTester(
      App.creates.remove_tag.operation.perform,
      bundle({ inputData: { contact_id: CONTACT, tag_id: 't1' } }),
    );
  });

  it('an unknown tag is the API’s own message', async () => {
    nock(API)
      .post(`/public/v1/contacts/${CONTACT}/tags`)
      .reply(404, { code: 'not_found', detail: 'One of those tags wasn’t found.' });
    await expect(
      appTester(
        App.creates.add_tag.operation.perform,
        bundle({ inputData: { contact_id: CONTACT, tag_id: 'gone' } }),
      ),
    ).rejects.toThrow('One of those tags wasn’t found.');
  });

  it('set field sends one custom field, and an empty value clears it', async () => {
    nock(API, auth).patch(`/public/v1/contacts/${CONTACT}`, { fields: { city: 'Pune' } }).reply(200, record);
    await appTester(
      App.creates.set_field.operation.perform,
      bundle({ inputData: { contact_id: CONTACT, field_key: 'city', value: 'Pune' } }),
    );
    nock(API, auth).patch(`/public/v1/contacts/${CONTACT}`, { fields: { city: null } }).reply(200, record);
    await appTester(
      App.creates.set_field.operation.perform,
      bundle({ inputData: { contact_id: CONTACT, field_key: 'city', value: '' } }),
    );
  });

  it('set field shows the API’s message for a value that does not fit', async () => {
    nock(API)
      .patch(`/public/v1/contacts/${CONTACT}`)
      .reply(422, { code: 'validation_error', title: 'The request is not valid', errors: [] });
    await expect(
      appTester(
        App.creates.set_field.operation.perform,
        bundle({ inputData: { contact_id: CONTACT, field_key: 'size', value: 'XXL' } }),
      ),
    ).rejects.toThrow('The request is not valid');
  });

  describe('send message', () => {
    const inputData = { conversation_id: '9a8b7c6d', text: 'Yes, we ship to Pune.' };

    it('sends the text with an idempotency key', async () => {
      let sent;
      nock(API, auth)
        .post('/public/v1/conversations/9a8b7c6d/messages', { text: inputData.text })
        .reply(202, function reply() {
          sent = this.req.headers['idempotency-key'];
          return { id: 'm1', status: 'queued', text: inputData.text, conversation_id: '9a8b7c6d' };
        });
      const result = await appTester(App.creates.send_message.operation.perform, bundle({ inputData }));
      expect(result.status).toBe('queued');
      expect(sent).toMatch(/^zap-[0-9a-f]{40}$/);
    });

    it('the same step retried inside five minutes uses the same key; another text or window does not', () => {
      const now = Date.UTC(2026, 9, 24, 10, 0, 0);
      const key = idempotencyKey('c1', 'Hello', now);
      expect(idempotencyKey('c1', 'Hello', now + 1000)).toBe(key);
      expect(idempotencyKey('c1', 'Hello again', now)).not.toBe(key);
      expect(idempotencyKey('c2', 'Hello', now)).not.toBe(key);
      expect(idempotencyKey('c1', 'Hello', now + RETRY_WINDOW_MS)).not.toBe(key);
    });

    it('outside the reply window the API’s message is shown', async () => {
      nock(API)
        .post('/public/v1/conversations/9a8b7c6d/messages')
        .reply(409, {
          code: 'reply_window_closed',
          detail: 'The 24-hour reply window has closed.',
        });
      await expect(
        appTester(App.creates.send_message.operation.perform, bundle({ inputData })),
      ).rejects.toThrow('The 24-hour reply window has closed.');
    });
  });

  it('every action has input fields and a sample', () => {
    for (const key of ['add_tag', 'remove_tag', 'set_field', 'send_message']) {
      expect(App.creates[key].operation.inputFields.length).toBeGreaterThan(0);
      expect(App.creates[key].operation.sample.id || App.creates[key].operation.sample.name).toBeTruthy();
    }
  });
});
