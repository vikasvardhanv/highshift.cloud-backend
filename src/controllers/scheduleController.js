const Joi = require('joi');
const mongoose = require('mongoose');
const { AppError } = require('../utils/errors');
const ScheduledPost = require('../models/ScheduledPost');
const { agenda } = require('../services/scheduler');

const scheduleSchema = Joi.object({
    accounts: Joi.array().items(Joi.object({
        platform: Joi.string().valid('twitter', 'facebook', 'instagram', 'linkedin', 'youtube').required(),
        accountId: Joi.string().required()
    })).min(1).required(),
    content: Joi.string().min(1).max(2800).required(),
    media: Joi.array().items(Joi.string().max(2_000_000)).max(4).optional(),
    scheduledFor: Joi.date().greater('now').required()
}).required();

async function createScheduledPost(req, res, next) {
    try {
        const { error, value } = scheduleSchema.validate(req.body, { stripUnknown: true });
        if (error) throw new AppError('Validation error', 400, 'validation_error', error.details);

        const post = new ScheduledPost({
            userId: req.user._id,
            accounts: value.accounts,
            content: value.content,
            media: value.media,
            scheduledFor: value.scheduledFor,
            status: 'pending'
        });

        await post.save();

        // Schedule the job in Agenda
        const job = await agenda.schedule(value.scheduledFor, 'publish_scheduled_post', { scheduledPostId: post._id });

        post.jobId = job.attrs._id.toString();
        await post.save();

        res.status(201).json({ ok: true, scheduledPost: post });
    } catch (err) {
        next(err);
    }
}

async function listScheduledPosts(req, res, next) {
    try {
        const posts = await ScheduledPost.find({ userId: req.user._id })
            .sort({ scheduledFor: -1 })
            .limit(50);
        res.json({ ok: true, posts });
    } catch (err) {
        next(err);
    }
}

async function cancelScheduledPost(req, res, next) {
    try {
        const post = await ScheduledPost.findOne({ _id: req.params.id, userId: req.user._id });
        if (!post) throw new AppError('Post not found', 404, 'post_not_found');

        if (post.status !== 'pending') {
            throw new AppError('Cannot cancel non-pending post', 400, 'post_not_pending');
        }

        if (post.jobId) {
            await agenda.cancel({ _id: mongoose.Types.ObjectId(post.jobId) });
        }

        post.status = 'canceled';
        await post.save();

        res.json({ ok: true, message: 'Post canceled' });
    } catch (err) {
        next(err);
    }
}

module.exports = { createScheduledPost, listScheduledPosts, cancelScheduledPost };
