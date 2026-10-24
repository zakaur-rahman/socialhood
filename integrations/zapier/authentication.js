'use strict';

const { apiBase } = require('./lib/api');

/**
 * Connect with a workspace API key (Settings, Integrations, API keys). The test call is GET
 * /public/v1/me, which any valid key can make; it returns the workspace's name, which labels the
 * connection ("Maple Bakery") so a person with two workspaces can tell them apart.
 */
module.exports = {
  type: 'custom',
  fields: [
    {
      key: 'api_key',
      label: 'API key',
      type: 'password',
      required: true,
      helpText:
        'Make a key in Social Hood under **Settings, Integrations, API keys** (Pro and Max plans). ' +
        'For this app, give it the scopes `contacts:read`, `contacts:write`, `tags:read`, ' +
        '`tags:write`, `conversations:read`, `messages:send`, `automations:read` and ' +
        '`webhooks:subscribe`, or only those for the steps your Zaps use.',
    },
  ],
  test: async (z) => {
    const response = await z.request({ url: `${apiBase()}/me` });
    return {
      workspace_name: response.data.workspace_name,
      workspace_id: response.data.workspace_id,
      scopes: response.data.scopes,
    };
  },
  connectionLabel: '{{workspace_name}}',
};
