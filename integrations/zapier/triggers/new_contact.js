'use strict';

const { apiBase, contactRef } = require('../lib/api');
const hookTrigger = require('../lib/hook');

const CONTACT = {
  id: '5b1b3f1e-6a53-4b4e-8f0e-2d2b9a7c1a11',
  platform: 'instagram',
  username: 'priya.shah',
  name: 'Priya Shah',
};

// New Contact: a person wrote, commented or opened an entry link for the first time
// (event contact.created). Polling lists contacts newest first.
module.exports = hookTrigger({
  key: 'new_contact',
  noun: 'Contact',
  label: 'New Contact',
  description: 'Triggers when a new person writes, comments or opens an entry link.',
  trigger: 'new_contact',
  sample: {
    id: 'e1c9a8a0-3b8e-4f0e-9c52-6d1d3f0a1b01',
    event: 'contact.created',
    occurred_at: '2026-10-24T09:30:00+00:00',
    workspace_id: '0b7d9d0e-3f2a-4e53-8b61-0a4c5d6e7f80',
    contact: CONTACT,
  },
  outputFields: [
    { key: 'contact__id', label: 'Contact ID' },
    { key: 'contact__name', label: 'Name' },
    { key: 'contact__username', label: 'Username' },
    { key: 'contact__platform', label: 'Platform' },
    { key: 'occurred_at', label: 'When', type: 'datetime' },
  ],
  list: async (z) => {
    const response = await z.request({
      url: `${apiBase()}/contacts`,
      params: { sort: 'created', limit: 10 },
    });
    return response.data.items.map((c) => ({
      id: c.id,
      event: 'contact.created',
      occurred_at: c.first_seen_at,
      contact: contactRef(c),
    }));
  },
});
