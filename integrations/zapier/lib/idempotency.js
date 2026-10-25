'use strict';

const crypto = require('crypto');

// Five minutes: Zapier retrying a step inside this window sends the message once.
const RETRY_WINDOW_MS = 5 * 60 * 1000;

/**
 * The Idempotency-Key for a send: the same conversation, text and five-minute window give the same
 * key, so a retried step does not message the customer twice. The API returns the first response
 * for a repeated key.
 */
const idempotencyKey = (conversationId, text, now = Date.now()) =>
  'zap-' +
  crypto
    .createHash('sha256')
    .update(`${conversationId}
${text}
${Math.floor(now / RETRY_WINDOW_MS)}`)
    .digest('hex')
    .slice(0, 40);

module.exports = { idempotencyKey, RETRY_WINDOW_MS };
