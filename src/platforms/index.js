const twitter = require('./twitter');
const facebook = require('./facebook');
const instagram = require('./instagram');
const linkedin = require('./linkedin');
const youtube = require('./youtube');

const adapters = { twitter, facebook, instagram, linkedin, youtube };

function getAdapter(platform) {
  const a = adapters[String(platform || '').toLowerCase()];
  return a || null;
}

module.exports = { getAdapter, adapters };
