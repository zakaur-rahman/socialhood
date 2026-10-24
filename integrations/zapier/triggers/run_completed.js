'use strict';

const { apiBase, contactRef } = require('../lib/api');
const hookTrigger = require('../lib/hook');

// Automation Run Completed: an automation finished a run (event automation.run.completed).
// Polling lists the latest runs, newest first.
module.exports = hookTrigger({
  key: 'run_completed',
  noun: 'Automation Run',
  label: 'Automation Run Completed',
  description: 'Triggers when an automation finishes a run for a customer.',
  trigger: 'run_completed',
  sample: {
    id: 'd3c2b1a0-4e5f-4a6b-9c7d-8e9f0a1b2c08',
    event: 'automation.run.completed',
    occurred_at: '2026-10-24T10:30:00+00:00',
    workspace_id: '0b7d9d0e-3f2a-4e53-8b61-0a4c5d6e7f80',
    run: { id: 'c2b2f3a4-0f55-4d3a-8f3b-6e8c9d0a1b33', result: 'sent', trigger: 'dm_keyword' },
    automation: { id: '7c5f0c9e-1d7a-4f43-9a35-2a7f0b0c2a22', name: 'Send the price list' },
    contact: {
      id: '5b1b3f1e-6a53-4b4e-8f0e-2d2b9a7c1a11',
      platform: 'instagram',
      username: 'priya.shah',
      name: 'Priya Shah',
    },
  },
  outputFields: [
    { key: 'run__id', label: 'Run ID' },
    { key: 'run__result', label: 'Result' },
    { key: 'automation__name', label: 'Automation' },
    { key: 'contact__id', label: 'Contact ID' },
    { key: 'contact__name', label: 'Name' },
    { key: 'occurred_at', label: 'When', type: 'datetime' },
  ],
  list: async (z) => {
    const response = await z.request({
      url: `${apiBase()}/automation-runs`,
      params: { limit: 10 },
    });
    return response.data.items.map((r) => ({
      id: r.id,
      event: 'automation.run.completed',
      occurred_at: r.created_at,
      run: { id: r.id, result: r.result, trigger: r.trigger_kind },
      contact: r.contact
        ? contactRef({ ...r.contact, platform: null, name: r.contact.display_name })
        : null,
    }));
  },
});
