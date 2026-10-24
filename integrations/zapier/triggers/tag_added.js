'use strict';

const { apiBase, contactRef } = require('../lib/api');
const hookTrigger = require('../lib/hook');

// Tag Added: a tag was put on a contact (event contact.tagged; the API also sends removals, which
// this trigger drops). Pick a tag to hear about only that one. Polling lists that tag's contacts.
module.exports = hookTrigger({
  key: 'tag_added',
  noun: 'Tag',
  label: 'Tag Added to Contact',
  description: 'Triggers when a tag is added to a contact.',
  trigger: 'tag_added',
  inputFields: [
    {
      key: 'tag_id',
      label: 'Tag',
      helpText: 'Leave empty to trigger for any tag.',
      dynamic: 'tag.id.name',
      required: false,
    },
  ],
  accept: (item, bundle) =>
    item.action === 'added' &&
    (!bundle.inputData.tag_id || (item.tag && item.tag.id === bundle.inputData.tag_id)),
  sample: {
    id: 'f7e3c1d0-8a14-4b53-b9c1-4e2a3d5b6c03',
    event: 'contact.tagged',
    occurred_at: '2026-10-24T10:05:00+00:00',
    workspace_id: '0b7d9d0e-3f2a-4e53-8b61-0a4c5d6e7f80',
    contact: {
      id: '5b1b3f1e-6a53-4b4e-8f0e-2d2b9a7c1a11',
      platform: 'instagram',
      username: 'priya.shah',
      name: 'Priya Shah',
    },
    tag: { id: '3d9e2b1c-6f4a-4c7d-9e8b-1a2b3c4d5e04', name: 'VIP' },
    action: 'added',
  },
  outputFields: [
    { key: 'tag__id', label: 'Tag ID' },
    { key: 'tag__name', label: 'Tag' },
    { key: 'contact__id', label: 'Contact ID' },
    { key: 'contact__name', label: 'Name' },
    { key: 'contact__username', label: 'Username' },
    { key: 'occurred_at', label: 'When', type: 'datetime' },
  ],
  list: async (z, bundle) => {
    const tagId = bundle.inputData.tag_id;
    const tags = await z.request({ url: `${apiBase()}/tags` });
    const tag = tagId ? tags.data.items.find((t) => t.id === tagId) : tags.data.items[0];
    if (!tag) {
      return [];
    }
    const response = await z.request({
      url: `${apiBase()}/contacts`,
      params: { sort: 'created', tag_id: tag.id, limit: 10 },
    });
    return response.data.items.map((c) => ({
      id: `${c.id}:${tag.id}`,
      event: 'contact.tagged',
      occurred_at: c.first_seen_at,
      contact: contactRef(c),
      tag: { id: tag.id, name: tag.name },
      action: 'added',
    }));
  },
});
