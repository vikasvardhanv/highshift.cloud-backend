const express = require('express');
const helmet = require('helmet');
const cors = require('cors');
const morgan = require('morgan');

const connectRoutes = require('./routes/connectRoutes');
const accountRoutes = require('./routes/accountRoutes');
const postRoutes = require('./routes/postRoutes');
const scheduleRoutes = require('./routes/scheduleRoutes');
const analyticsRoutes = require('./routes/analyticsRoutes');
const brandRoutes = require('./routes/brandRoutes');
const aiRoutes = require('./routes/aiRoutes');
const keyRoutes = require('./routes/keyRoutes');

const { apiRateLimiter, ipRateLimiter } = require('./middlewares/rateLimiters');
const { requestLogger } = require('./middlewares/requestLogger');
const { errorHandler, notFound } = require('./middlewares/errorHandlers');

const swagger = require('./swagger');

const app = express();

app.set('trust proxy', 1);

// Security headers
app.use(helmet());

// Body parsing (reasonable defaults)
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// CORS allowlist
const allowedOrigins = (process.env.CORS_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean);
app.use(cors({
  origin: function (origin, cb) {
    if (!origin) return cb(null, true); // allow server-to-server / curl
    if (!allowedOrigins.length) return cb(null, true);
    if (allowedOrigins.includes(origin)) return cb(null, true);
    return cb(new Error('CORS blocked'), false);
  },
  credentials: false
}));

// Logging
app.use(morgan('combined'));
app.use(requestLogger);

// Rate limit: IP on all routes, API-key on protected routes
app.use(ipRateLimiter);

// Swagger
swagger(app);

// Routes
app.get('/health', (req, res) => res.json({ ok: true }));

app.use('/connect', connectRoutes);            // unauthenticated
app.use('/linked-accounts', apiRateLimiter, accountRoutes);
app.use('/post', apiRateLimiter, postRoutes);
app.use('/schedule', apiRateLimiter, scheduleRoutes);
app.use('/analytics', apiRateLimiter, analyticsRoutes);
app.use('/brand', apiRateLimiter, brandRoutes);
app.use('/ai', apiRateLimiter, aiRoutes);
app.use('/', apiRateLimiter, keyRoutes);

// Serve Frontend in Production
// Serve Frontend in Production (Hybrid Mode)
// Only serve if the frontend build exists (e.g. monolithic deployment)
if (process.env.NODE_ENV === 'production') {
  const path = require('path');
  const fs = require('fs');
  const distPath = path.join(__dirname, '../frontend/dist');

  if (fs.existsSync(distPath)) {
    // Serve static files from the frontend build directory
    app.use(express.static(distPath));

    // Handle SPA client-side routing
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  } else {
    // If running as pure API backend, just return 404 for unknown routes
    logger.info('Running in API-only mode (frontend build not found)');
  }
}

// 404 + error handler
app.use(notFound);
app.use(errorHandler);

module.exports = app;
