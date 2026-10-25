'use strict';

const nock = require('nock');

const { App, appTester, API, KEY, bundle, delivery, contact } = require('./helpers');

const TARGET = 'https://hooks.zapier.com/hooks/standard/1/abc/';
const auth = { reqheaders: { authorization: `Bearer ${KEY}` } };

const TRIGGERS = {
  new_contact: 'contact.created',
  lead_captured: 'lead.captured',
  tag_added: 'contact.tagged',
  new_message: 'message.received',
  run_completed: 'automation.run.completed',
};

describe('REST hook triggers', () => {
  afterEach(() => nock.cleanAll());

  it.each(Object.keys(TRIGGERS))('%s subscribes with the Zap’s target URL', async (key) => {
    nock(API, auth)
      .post('/public/v1/hooks', { trigger: key, target_url: TARGET })
      .reply(201, { id: 'h1', trigger: key, target_url: TARGET, status: 'active', signing_secret: 'whsec_x' });
    const result = await appTester(App.triggers[key].operation.performSubscribe, bundle({ targetUrl: TARGET }));
    expect(result.id).toBe('h1'); // Zapier keeps it as subscribeData
  });

  it.each(Object.keys(TRIGGERS))('%s unsubscribes by the subscribed id', async (key) => {
    nock(API, auth).delete('/public/v1/hooks/h1').reply(204);
    const result = await appTester(
      App.triggers[key].operation.performUnsubscribe,
      bundle({ subscribeData: { id: 'h1' } }),
    );
    expect(result).toEqual({});
  });

  it('unsubscribing a hook that is already gone is not an error', async () => {
    nock(API).delete('/public/v1/hooks/h1').reply(404, { code: 'not_found', detail: 'That hook wasn’t found.' });
    const result = await appTester(
      App.triggers.new_contact.operation.performUnsubscribe,
      bundle({ subscribeData: { id: 'h1' } }),
    );
    expect(result).toEqual({});
  });

  it('turns a delivery into one item keyed by the event id', async () => {
    const event = delivery('contact.created', { contact });
    const items = await appTester(
      App.triggers.new_contact.operation.perform,
      bundle({ cleanedRequest: event }),
    );
    expect(items).toEqual([
      {
        id: event.id,
        event: 'contact.created',
        occurred_at: event.created_at,
        workspace_id: event.workspace_id,
        contact,
      },
    ]);
  });

  it('lead captured carries what was captured', async () => {
    const event = delivery('lead.captured', {
      contact,
      captured: { kind: 'email', field_key: null, value: 'priya@example.com' },
      automation: { id: 'a1', name: 'Send the price list' },
      run_id: 'r1',
    });
    const [item] = await appTester(
      App.triggers.lead_captured.operation.perform,
      bundle({ cleanedRequest: event }),
    );
    expect(item.captured.value).toBe('priya@example.com');
    expect(item.automation.name).toBe('Send the price list');
  });

  describe('tag added', () => {
    const tagged = (action, tagId = 't1') =>
      delivery('contact.tagged', { contact, tag: { id: tagId, name: 'VIP' }, action });

    it('passes additions and drops removals', async () => {
      const perform = App.triggers.tag_added.operation.perform;
      expect(await appTester(perform, bundle({ cleanedRequest: tagged('added') }))).toHaveLength(1);
      expect(await appTester(perform, bundle({ cleanedRequest: tagged('removed') }))).toEqual([]);
    });

    it('keeps only the tag the Zap asked for', async () => {
      const perform = App.triggers.tag_added.operation.perform;
      const inputData = { tag_id: 't1' };
      expect(await appTester(perform, bundle({ inputData, cleanedRequest: tagged('added', 't1') }))).toHaveLength(1);
      expect(await appTester(perform, bundle({ inputData, cleanedRequest: tagged('added', 't2') }))).toEqual([]);
    });
  });

  describe('polling lists (sample data and tests), newest first', () => {
    const list = (key, inputData = {}) => appTester(App.triggers[key].operation.performList, bundle({ inputData }));
    const person = { ...contact, email: 'priya@example.com', first_seen_at: '2026-10-24T09:00:00Z' };

    it('new contact lists contacts by created', async () => {
      nock(API, auth)
        .get('/public/v1/contacts')
        .query({ sort: 'created', limit: 10 })
        .reply(200, { items: [person], next_cursor: null });
      const [item] = await list('new_contact');
      expect(item).toMatchObject({ id: contact.id, event: 'contact.created', contact });
    });

    it('lead captured lists contacts that have an email', async () => {
      nock(API, auth)
        .get('/public/v1/contacts')
        .query({ sort: 'created', has_email: true, limit: 10 })
        .reply(200, { items: [person], next_cursor: null });
      const [item] = await list('lead_captured');
      expect(item.captured).toEqual({ kind: 'email', field_key: null, value: 'priya@example.com' });
    });

    it('tag added lists the chosen tag’s contacts, one item per contact and tag', async () => {
      nock(API, auth).get('/public/v1/tags').reply(200, { items: [{ id: 't1', name: 'VIP' }] });
      nock(API, auth)
        .get('/public/v1/contacts')
        .query({ sort: 'created', tag_id: 't1', limit: 10 })
        .reply(200, { items: [person], next_cursor: null });
      const [item] = await list('tag_added', { tag_id: 't1' });
      expect(item).toMatchObject({ id: `${contact.id}:t1`, action: 'added', tag: { id: 't1', name: 'VIP' } });
    });

    it('tag added with no tags has nothing to list', async () => {
      nock(API, auth).get('/public/v1/tags').reply(200, { items: [] });
      expect(await list('tag_added')).toEqual([]);
    });

    it('new message lists conversations whose last message is the customer’s', async () => {
      const conversation = (id, direction) => ({
        id,
        platform: 'instagram',
        contact: { id: contact.id, display_name: 'Priya Shah', username: 'priya.shah' },
        last_message_at: '2026-10-24T10:20:00Z',
        last_message_preview: 'Do you ship to Pune?',
        last_message_direction: direction,
        last_message_kind: 'text',
      });
      nock(API, auth)
        .get('/public/v1/conversations')
        .query({ limit: 10 })
        .reply(200, { items: [conversation('c1', 'inbound'), conversation('c2', 'outbound')], next_cursor: null });
      const items = await list('new_message');
      expect(items).toHaveLength(1);
      expect(items[0]).toMatchObject({
        conversation_id: 'c1',
        contact: { name: 'Priya Shah', platform: 'instagram' },
        message: { text: 'Do you ship to Pune?' },
      });
    });

    it('run completed lists runs', async () => {
      nock(API, auth)
        .get('/public/v1/automation-runs')
        .query({ limit: 10 })
        .reply(200, {
          items: [
            {
              id: 'r1',
              created_at: '2026-10-24T10:30:00Z',
              trigger_kind: 'dm',
              result: 'sent',
              contact: { id: contact.id, display_name: 'Priya Shah', username: 'priya.shah' },
            },
          ],
          next_cursor: null,
        });
      const [item] = await list('run_completed');
      expect(item).toMatchObject({ id: 'r1', run: { result: 'sent', trigger: 'dm' } });
    });
  });

  it('the dropdown triggers are hidden and list tags and fields', async () => {
    expect(App.triggers.tag.display.hidden).toBe(true);
    expect(App.triggers.contact_field.display.hidden).toBe(true);
    nock(API, auth).get('/public/v1/tags').reply(200, { items: [{ id: 't1', name: 'VIP', color: 1 }] });
    expect(await appTester(App.triggers.tag.operation.perform, bundle())).toEqual([{ id: 't1', name: 'VIP' }]);
    nock(API, auth)
      .get('/public/v1/contact-fields')
      .reply(200, { items: [{ key: 'city', label: 'City', type: 'text' }] });
    const [field] = await appTester(App.triggers.contact_field.operation.perform, bundle());
    expect(field.key).toBe('city');
  });

  it('every trigger has a sample and a polling list', () => {
    for (const key of Object.keys(TRIGGERS)) {
      const operation = App.triggers[key].operation;
      expect(operation.type).toBe('hook');
      expect(operation.sample.id).toBeTruthy();
      expect(typeof operation.performList).toBe('function');
    }
  });
});
