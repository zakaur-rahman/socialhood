'use strict';

const zapier = require('zapier-platform-core');

const App = require('../index');

process.env.API_BASE_URL = 'https://api.example.test';

const appTester = zapier.createAppTester(App);

const API = 'https://api.example.test';
const KEY = 'shk_test_0000000000000000000000000000000000';

/** A bundle as Zapier builds it: the connection's key and the step's settings. */
const bundle = (extra = {}) => ({
  authData: { api_key: KEY },
  inputData: {},
  ...extra,
});

/** A REST hook delivery, as GR-04's machinery sends it (services/webhooks/events.py). */
const delivery = (type, data, id = 'e1c9a8a0-3b8e-4f0e-9c52-6d1d3f0a1b01') => ({
  id,
  type,
  version: 1,
  created_at: '2026-10-24T09:30:00+00:00',
  workspace_id: '0b7d9d0e-3f2a-4e53-8b61-0a4c5d6e7f80',
  data,
});

const contact = {
  id: '5b1b3f1e-6a53-4b4e-8f0e-2d2b9a7c1a11',
  platform: 'instagram',
  username: 'priya.shah',
  name: 'Priya Shah',
};

module.exports = { App, appTester, API, KEY, bundle, delivery, contact };
