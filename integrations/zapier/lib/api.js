'use strict';

/**
 * What the app shares: where the public API is, how a request is made and how its answers are
 * turned into the shape the triggers send (the same shape as a REST hook delivery, so a Zap tested
 * with a polled sample works the same when a real event arrives).
 */

// Set with `zapier env:set <version> API_BASE_URL=...`; the default is the production API.
const apiBase = () => `${process.env.API_BASE_URL || 'https://api.socialhood.com'}/public/v1`;

/** The API's problem+json error as a Zapier error (its detail is written for people). */
const handleErrors = (response, z) => {
  if (response.status < 400) {
    return response;
  }
  let problem = {};
  try {
    problem = response.data || JSON.parse(response.content);
  } catch (error) {
    // not JSON: fall through to the generic message
  }
  const detail = problem.detail || problem.title || `Social Hood answered ${response.status}.`;
  const message =
    response.status === 401
      ? 'Your Social Hood API key was not accepted. Make a new key in Settings, Integrations.'
      : detail;
  throw new z.errors.Error(message, problem.code || 'api_error', response.status);
};

/** Adds the API key from the connection to every request. */
const addApiKey = (request, z, bundle) => {
  request.headers = request.headers || {};
  request.headers.Authorization = `Bearer ${bundle.authData.api_key}`;
  request.headers.Accept = 'application/json';
  return request;
};

/** A contact the way events refer to one: id, platform, @username and name. */
const contactRef = (contact) => ({
  id: contact.id,
  platform: contact.platform,
  username: contact.username || null,
  name: contact.name,
});

/** The event envelope (services/webhooks/events.py) as one flat-ish item for Zapier. */
const fromEvent = (event) => ({
  id: event.id,
  event: event.type,
  occurred_at: event.created_at,
  workspace_id: event.workspace_id,
  ...event.data,
});

module.exports = { apiBase, handleErrors, addApiKey, contactRef, fromEvent };
