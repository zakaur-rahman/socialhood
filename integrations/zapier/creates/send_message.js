'use strict';

const { apiBase } = require('../lib/api');
const { idempotencyKey } = require('../lib/idempotency');

// Send Message: POST /conversations/{id}/messages. The platform's rules apply as in the app: it
// works only inside the reply window (24 hours from the customer's last message), and the error
// says so when the window has closed.
module.exports = {
  key: 'send_message',
  noun: 'Message',
  display: {
    label: 'Send Message',
    description:
      'Sends a text message in a conversation. Works only inside the 24-hour reply window.',
  },
  operation: {
    inputFields: [
      {
        key: 'conversation_id',
        label: 'Conversation ID',
        required: true,
        helpText: 'Map it from New Message from Customer’s **Conversation ID**.',
      },
      { key: 'text', label: 'Message', required: true, type: 'text' },
    ],
    perform: async (z, bundle) => {
      const { conversation_id: conversationId, text } = bundle.inputData;
      const response = await z.request({
        method: 'POST',
        url: `${apiBase()}/conversations/${conversationId}/messages`,
        headers: { 'Idempotency-Key': idempotencyKey(conversationId, text) },
        body: { text },
      });
      return response.data;
    },
    sample: {
      id: '1f2e3d4c-5b6a-4978-8695-a4b3c2d1e007',
      conversation_id: '9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c06',
      direction: 'outbound',
      kind: 'text',
      text: 'Yes, we ship to Pune.',
      status: 'queued',
      occurred_at: '2026-10-24T10:21:00+00:00',
    },
    outputFields: [
      { key: 'id', label: 'Message ID' },
      { key: 'conversation_id', label: 'Conversation ID' },
      { key: 'text', label: 'Message' },
      { key: 'status', label: 'Status' },
    ],
  },
};
