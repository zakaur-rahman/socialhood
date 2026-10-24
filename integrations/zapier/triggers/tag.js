'use strict';

const { apiBase } = require('../lib/api');

// Hidden: fills the Tag dropdowns (Tag Added, Add Tag, Remove Tag).
module.exports = {
  key: 'tag',
  noun: 'Tag',
  display: { label: 'Tag', description: 'Lists your tags.', hidden: true },
  operation: {
    perform: async (z) => {
      const response = await z.request({ url: `${apiBase()}/tags` });
      return response.data.items.map((t) => ({ id: t.id, name: t.name }));
    },
    sample: { id: '3d9e2b1c-6f4a-4c7d-9e8b-1a2b3c4d5e04', name: 'VIP' },
  },
};
