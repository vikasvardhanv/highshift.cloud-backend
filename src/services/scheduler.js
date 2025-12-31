const Agenda = require('agenda');
const logger = require('../utils/logger');
const ScheduledPost = require('../models/ScheduledPost');
const User = require('../models/User');
const { getAdapter } = require('../platforms');
const { ensureValidAccessToken } = require('./tokenService');

const agenda = new Agenda({
    db: { address: process.env.MONGODB_URI, collection: 'agendaJobs' },
    processEvery: '1 minute'
});

agenda.define('publish_scheduled_post', async (job) => {
    const { scheduledPostId } = job.attrs.data;
    logger.info(`Processing scheduled post: ${scheduledPostId}`);

    const post = await ScheduledPost.findById(scheduledPostId);
    if (!post) {
        logger.error(`Scheduled post not found: ${scheduledPostId}`);
        return;
    }

    if (post.status === 'canceled') {
        logger.info('Scheduled post was canceled, skipping.');
        return;
    }

    post.status = 'processing';
    await post.save();

    const results = {};
    const user = await User.findById(post.userId);

    if (!user) {
        post.status = 'failed';
        post.error = 'User not found';
        await post.save();
        return;
    }

    for (const target of post.accounts) {
        const { platform, accountId } = target;
        const key = `${platform}:${accountId}`;

        try {
            // 1. Get Adapter
            const adapter = getAdapter(platform);
            if (!adapter) throw new Error(`Unsupported platform: ${platform}`);

            // 2. Find Linked Account
            const linked = user.linkedAccounts.id(accountId);
            if (!linked) throw new Error('Linked account not found or deleted');

            // 3. Get Token
            const { accessToken } = await ensureValidAccessToken(user._id, linked._id);

            // 4. Publish
            let result;
            if (platform === 'instagram') {
                const imageUrl = post.media?.[0];
                if (!imageUrl) throw new Error('Instagram requires an image');
                result = await adapter.publishImage({
                    accessToken,
                    igUserId: linked.accountId,
                    caption: post.content,
                    imageUrl
                });
            } else {
                result = await adapter.post({
                    accessToken,
                    content: post.content,
                    media: post.media,
                    accountId: linked.accountId
                });
            }

            results[key] = { ok: true, result };

        } catch (err) {
            logger.error(`Failed to publish to ${key}`, { err });
            results[key] = { ok: false, error: err.message };
        }
    }

    // Determine final status
    const allFailed = Object.values(results).every(r => !r.ok);
    const someFailed = Object.values(results).some(r => !r.ok);

    post.result = results;
    post.status = allFailed ? 'failed' : (someFailed ? 'partial' : 'published');

    if (allFailed) post.error = 'All targets failed';

    await post.save();
    logger.info(`Scheduled post processed. Status: ${post.status}`);
});

async function startScheduler() {
    await agenda.start();
    logger.info('Agenda scheduler started');
}

module.exports = { agenda, startScheduler };
