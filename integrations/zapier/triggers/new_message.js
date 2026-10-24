'use strict';

const { apiBase, contactRef } = require('../lib/api');
const hookTrigger = require('../lib/hook');

// New Message: a customer sent a direct message (event message.received). Polling lists the
// conversations whose latest message is from the customer, newest first.
module.exports = hookTrigger({
  key: 'new_message',
  noun: 'Message',
  label: 'New Message from Customer',
  description: 'Triggers when a customer sends a direct message on Instagram or WhatsApp.',
  trigger: 'new_message',
  sample: {
    id: 'b8d4e2f1-9c25-4a63-8d70-5f3b4e6c7d05',
    event: 'message.received',
    occurred_at: '2026-10-24T10:20:00+00:00',
    workspace_id: '0b7d9d0e-3f2a-4e53-8b61-0a4c5d6e7f80',
    contact: {
      id: '5b1b3f1e-6a53-4b4e-8f0e-2d2b9a7c1a11',
      platform: 'instagram',
      username: 'priya.shah',
      name: 'Priya Shah',
    },
    conversation_id: '9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c06',
    message: {
      id: '1f2e3d4c-5b6a-4978-8695-a4b3c2d1e007',
      kind: 'text',
      text: 'Do you ship to Pune?',
      occurred_at: '2026-10-24T10:20:00+00:00',
    },
  },
  outputFields: [
    { key: 'message__text', label: 'Message' },
    { key: 'message__id', label: 'Message ID' },
    { key: 'conversation_id', label: 'Conversation ID' },
    { key: 'contact__id', label: 'Contact ID' },
    { key: 'contact__name', label: 'Name' },
    { key: 'contact__username', label: 'Username' },
    { key: 'contact__platform', label: 'Platform' },
    { key: 'occurred_at', label: 'When', type: 'datetime' },
  ],
  list: async (z) => {
    const response = await z.request({
      url: `${apiBase()}/conversations`,
      params: { limit: 10 },
    });
    return response.data.items
      .filter((c) => c.last_message_direction === 'inbound')
      .map((c) => ({
        id: `${c.id}:${c.last_message_at}`,
        event: 'message.received',
        occurred_at: c.last_message_at,
        contact: contactRef({ ...c.contact, platform: c.platform, name: c.contact.display_name }),
        conversation_id: c.id,
        message: { text: c.last_message_preview, kind: c.last_message_kind, occurred_at: c.last_message_at },
      }));
  },
});
