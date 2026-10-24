'use strict';

const { apiBase } = require('../lib/api');

// Hidden: fills the Field dropdown of Set Contact Field with the workspace's custom fields.
module.exports = {
  key: 'contact_field',
  noun: 'Contact Field',
  display: { label: 'Contact Field', description: 'Lists your custom contact fields.', hidden: true },
  operation: {
    perform: async (z) => {
      const response = await z.request({ url: `${apiBase()}/contact-fields` });
      return response.data.items.map((f) => ({ id: f.key, key: f.key, label: f.label, type: f.type }));
    },
    sample: { id: 'city', key: 'city', label: 'City', type: 'text' },
  },
};
