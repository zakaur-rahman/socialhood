'use strict';

const { apiBase } = require('../lib/api');

// Set Contact Field: PATCH /contacts/{id} with one custom field. The API checks the value against
// the field's type (a choice field takes one of its choices); an empty value clears the field.
module.exports = {
  key: 'set_field',
  noun: 'Contact Field',
  display: {
    label: 'Set Contact Field',
    description: 'Sets a custom field on a contact, such as City or Order number.',
  },
  operation: {
    inputFields: [
      {
        key: 'contact_id',
        label: 'Contact ID',
        required: true,
        helpText: 'Map it from a trigger step, for example Lead Captured’s **Contact ID**.',
      },
      { key: 'field_key', label: 'Field', required: true, dynamic: 'contact_field.key.label' },
      {
        key: 'value',
        label: 'Value',
        helpText: 'Leave empty to clear the field.',
      },
    ],
    perform: async (z, bundle) => {
      const { contact_id: contactId, field_key: fieldKey, value } = bundle.inputData;
      const response = await z.request({
        method: 'PATCH',
        url: `${apiBase()}/contacts/${contactId}`,
        body: { fields: { [fieldKey]: value === undefined || value === '' ? null : value } },
      });
      return response.data;
    },
    sample: {
      id: '5b1b3f1e-6a53-4b4e-8f0e-2d2b9a7c1a11',
      name: 'Priya Shah',
      platform: 'instagram',
      username: 'priya.shah',
      fields: { city: 'Pune' },
    },
    outputFields: [
      { key: 'id', label: 'Contact ID' },
      { key: 'name', label: 'Name' },
      { key: 'username', label: 'Username' },
      { key: 'platform', label: 'Platform' },
    ],
  },
};
