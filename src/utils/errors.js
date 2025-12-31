class AppError extends Error {
  constructor(message, statusCode = 500, code = 'internal_error', details) {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
  }
}

module.exports = { AppError };
