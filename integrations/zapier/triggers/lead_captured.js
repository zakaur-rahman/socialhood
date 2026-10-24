'use strict';

const { apiBase, contactRef } = require('../lib/api');
const hookTrigger = require('../lib/hook');

// Lead Captured: an automation's question saved an email, a phone number or a field (event
// lead.captured). This is the trigger for "captured leads to a Google Sheet". Polling lists
// contacts that have an email, newest first (the sample a Zap is tested with).
module.exports = hookTrigger({
  key: 'lead_captured',
  noun: 'Lead',
  label: 'Lead Captured',
  description: 'Triggers when an automation captures a customer’s email, phone number or a field.',
  trigger: 'lead_captured',
  sample: {
    id: 'a4a1d0c2-52ab-4a53-a6f7-0d3a1c9a2b02',
    event: 'lead.captured',
    occurred_at: '2026-10-24T09:42:00+00:00',
    workspace_id: '0b7d9d0e-3f2a-4e53-8b61-0a4c5d6e7f80',
    contact: {
      id: '5b1b3f1e-6a53-4b4e-8f0e-2d2b9a7c1a11',
      platform: 'instagram',
      username: 'priya.shah',
      name: 'Priya Shah',
    },
    captured: { kind: 'email', field_key: null, value: 'priya@example.com' },
    automation: { id: '7c5f0c9e-1d7a-4f43-9a35-2a7f0b0c2a22', name: 'Send the price list' },
    run_id: 'c2b2f3a4-0f55-4d3a-8f3b-6e8c9d0a1b33',
  },
  outputFields: [
    { key: 'captured__kind', label: 'What was captured (email, phone or field)' },
    { key: 'captured__value', label: 'Value' },
    { key: 'captured__field_key', label: 'Field key' },
    { key: 'contact__id', label: 'Contact ID' },
    { key: 'contact__name', label: 'Name' },
    { key: 'contact__username', label: 'Username' },
    { key: 'contact__platform', label: 'Platform' },
    { key: 'automation__name', label: 'Automation' },
    { key: 'occurred_at', label: 'When', type: 'datetime' },
  ],
  list: async (z) => {
    const response = await z.request({
      url: `${apiBase()}/contacts`,
      params: { sort: 'created', has_email: true, limit: 10 },
    });
    return response.data.items.map((c) => ({
      id: c.id,
      event: 'lead.captured',
      occurred_at: c.first_seen_at,
      contact: contactRef(c),
      captured: { kind: 'email', field_key: null, value: c.email },
    }));
  },
});
