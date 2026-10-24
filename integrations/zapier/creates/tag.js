'use strict';

const { apiBase } = require('../lib/api');

const SAMPLE = {
  id: '5b1b3f1e-6a53-4b4e-8f0e-2d2b9a7c1a11',
  name: 'Priya Shah',
  platform: 'instagram',
  username: 'priya.shah',
  tags: [{ id: '3d9e2b1c-6f4a-4c7d-9e8b-1a2b3c4d5e04', name: 'VIP', color: 3 }],
};

const inputFields = [
  {
    key: 'contact_id',
    label: 'Contact ID',
    required: true,
    helpText: 'Map it from a trigger step, for example New Contact’s **Contact ID**.',
  },
  { key: 'tag_id', label: 'Tag', required: true, dynamic: 'tag.id.name' },
];

/** Add Tag and Remove Tag differ only in which side of POST /contacts/{id}/tags they fill. */
const tagAction = ({ key, label, description, side }) => ({
  key,
  noun: 'Tag',
  display: { label, description },
  operation: {
    inputFields,
    perform: async (z, bundle) => {
      const response = await z.request({
        method: 'POST',
        url: `${apiBase()}/contacts/${bundle.inputData.contact_id}/tags`,
        body: { [side]: [bundle.inputData.tag_id] },
      });
      return response.data;
    },
    sample: SAMPLE,
    outputFields: [
      { key: 'id', label: 'Contact ID' },
      { key: 'name', label: 'Name' },
      { key: 'username', label: 'Username' },
      { key: 'platform', label: 'Platform' },
    ],
  },
});

module.exports = {
  addTag: tagAction({
    key: 'add_tag',
    label: 'Add Tag to Contact',
    description: 'Puts a tag on a contact. Nothing changes if they already have it.',
    side: 'add',
  }),
  removeTag: tagAction({
    key: 'remove_tag',
    label: 'Remove Tag from Contact',
    description: 'Takes a tag off a contact. Nothing changes if they do not have it.',
    side: 'remove',
  }),
};
