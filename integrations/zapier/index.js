'use strict';

const { version: platformVersion } = require('zapier-platform-core');

const { version } = require('./package.json');
const authentication = require('./authentication');
const { addApiKey, handleErrors } = require('./lib/api');

const contactField = require('./triggers/contact_field');
const leadCaptured = require('./triggers/lead_captured');
const newContact = require('./triggers/new_contact');
const newMessage = require('./triggers/new_message');
const runCompleted = require('./triggers/run_completed');
const tag = require('./triggers/tag');
const tagAdded = require('./triggers/tag_added');

const { addTag, removeTag } = require('./creates/tag');
const sendMessage = require('./creates/send_message');
const setField = require('./creates/set_field');

// Social Hood for Zapier. Triggers are REST hooks (the API signs and retries each delivery);
// actions call the public API (/public/v1) with the connection's API key.
module.exports = {
  version,
  platformVersion,
  authentication,
  beforeRequest: [addApiKey],
  afterResponse: [handleErrors],
  triggers: {
    [newContact.key]: newContact,
    [leadCaptured.key]: leadCaptured,
    [tagAdded.key]: tagAdded,
    [newMessage.key]: newMessage,
    [runCompleted.key]: runCompleted,
    [tag.key]: tag,
    [contactField.key]: contactField,
  },
  creates: {
    [addTag.key]: addTag,
    [removeTag.key]: removeTag,
    [setField.key]: setField,
    [sendMessage.key]: sendMessage,
  },
  searches: {},
};
