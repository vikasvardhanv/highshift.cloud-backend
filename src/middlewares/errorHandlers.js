const logger = require('../utils/logger');
const { AppError } = require('../utils/errors');

function notFound(req, _res, next) {
  next(new AppError(`Route not found: ${req.method} ${req.originalUrl}`, 404, 'not_found'));
}

function errorHandler(err, _req, res, _next) {
  const status = err.statusCode || 500;
  const code = err.code || 'internal_error';

  if (status >= 500) {
    logger.error('error', { err });
  } else {
    logger.warn('client_error', { code, message: err.message, details: err.details });
  }

  res.status(status).json({
    error: {
      code,
      message: err.message,
      details: err.details
    }
  });
}

module.exports = { notFound, errorHandler };
