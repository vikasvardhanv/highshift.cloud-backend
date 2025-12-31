const mongoose = require('mongoose');

const LinkedAccountSchema = new mongoose.Schema({
  platform: { type: String, required: true, index: true },
  accountId: { type: String, required: true },
  username: { type: String },
  displayName: { type: String },
  accessTokenEnc: { type: String, required: true },
  refreshTokenEnc: { type: String },
  expiresAt: { type: Date },
  scope: { type: String },
  tokenType: { type: String },
  rawProfile: { type: Object },
}, { _id: true, timestamps: true });

const UserSchema = new mongoose.Schema({
  apiKeyHash: { type: String, unique: true, index: true, required: true },
  createdAt: { type: Date, default: Date.now },
  linkedAccounts: { type: [LinkedAccountSchema], default: [] }
}, { timestamps: true });

UserSchema.index({ 'linkedAccounts.platform': 1, 'linkedAccounts.accountId': 1 });

module.exports = mongoose.model('User', UserSchema);
