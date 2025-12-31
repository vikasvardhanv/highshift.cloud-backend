require('dotenv').config();
const mongoose = require('mongoose');
const app = require('./app');
const logger = require('./utils/logger');
const { startScheduler } = require('./services/scheduler');

const PORT = process.env.PORT || 3000;

async function start() {
  try {
    // Attempt MongoDB connection, but don't block server start on failure
    await mongoose.connect(process.env.MONGODB_URI, {
      autoIndex: true,
      serverSelectionTimeoutMS: 5000 // Fail fast if IP blocked
    });
    logger.info('MongoDB connected');

    await startScheduler();
    logger.info('Scheduler started');
  } catch (err) {
    logger.error('Failed to connect to MongoDB (starting server anyway)', { err });
    // We do NOT exit. We start the server so /health works and logs are visible.
  }

  app.listen(PORT, () => {
    logger.info(`Server listening on port ${PORT}`);
  });
}

start();
