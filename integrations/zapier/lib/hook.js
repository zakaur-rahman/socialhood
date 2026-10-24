'use strict';

const { apiBase, fromEvent } = require('./api');

/**
 * A REST hook trigger. Turning a Zap on subscribes (POST /public/v1/hooks with the Zap's target
 * URL); turning it off unsubscribes (DELETE /public/v1/hooks/{id}). Events arrive signed and
 * retried like any Social Hood webhook. `performList` is the polling fallback Zapier uses to test
 * the trigger and to fetch a sample: newest first, each item shaped like a delivery.
 *
 *   trigger       the name the API knows (new_contact, lead_captured, tag_added, new_message,
 *                 run_completed)
 *   accept        optional (data, bundle) => boolean: events a Zap's own settings filter out
 *   list          async (z, bundle) => items for performList
 */
module.exports = ({
  key,
  noun,
  label,
  description,
  trigger,
  sample,
  outputFields,
  inputFields = [],
  accept = () => true,
  list,
}) => ({
  key,
  noun,
  display: { label, description },
  operation: {
    type: 'hook',
    inputFields,
    performSubscribe: async (z, bundle) => {
      const response = await z.request({
        method: 'POST',
        url: `${apiBase()}/hooks`,
        body: { trigger, target_url: bundle.targetUrl },
      });
      // Zapier keeps this as bundle.subscribeData; the signing secret stays with it.
      return response.data;
    },
    performUnsubscribe: async (z, bundle) => {
      try {
        await z.request({
          method: 'DELETE',
          url: `${apiBase()}/hooks/${bundle.subscribeData.id}`,
        });
      } catch (error) {
        // Already gone (the key was revoked, which removes its hooks): nothing left to undo.
        if (error.status !== 404) {
          throw error;
        }
      }
      return {};
    },
    perform: async (z, bundle) => {
      const event = bundle.cleanedRequest;
      const item = fromEvent(event);
      return accept(item, bundle) ? [item] : [];
    },
    performList: list,
    sample,
    outputFields,
  },
});
