const mongoose = require('mongoose');

/**
 * Temporary state store for PKCE code_verifier.
 * TTL keeps the collection small and reduces replay risk.
 */
const OAuthStateSchema = new mongoose.Schema({
  state: { type: String, unique: true, required: true, index: true },
  platform: { type: String, required: true, index: true },
  codeVerifier: { type: String, required: true },
  // If linking additional accounts for an existing user, store the user id.
  userId: { type: mongoose.Schema.Types.ObjectId, ref: 'User' },
  // Optional client redirect override
  clientRedirect: { type: String },
  createdAt: { type: Date, default: Date.now, expires: 600 } // 10 minutes TTL
});

module.exports = mongoose.model('OAuthState', OAuthStateSchema);
