const express = require('express');
const router = express.Router();
const { createScheduledPost, listScheduledPosts, cancelScheduledPost } = require('../controllers/scheduleController');

/**
 * @route POST /schedule
 * @group Schedule - Post scheduling
 * @param {object} request.body.required - { accounts: [{platform, accountId}], content, media, scheduledFor: ISOString }
 * @security ApiKeyAuth
 */
router.post('/', createScheduledPost);

/**
 * @route GET /schedule
 * @group Schedule
 * @security ApiKeyAuth
 */
router.get('/', listScheduledPosts);

/**
 * @route DELETE /schedule/:id
 * @group Schedule
 * @security ApiKeyAuth
 */
router.delete('/:id', cancelScheduledPost);

module.exports = router;
