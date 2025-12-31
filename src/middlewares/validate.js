const { AppError } = require('../utils/errors');

function validate(schema, location = 'body') {
  return (req, _res, next) => {
    const data = req[location];
    const { error, value } = schema.validate(data, { abortEarly: false, stripUnknown: true });
    if (error) {
      return next(new AppError('Validation error', 400, 'validation_error', error.details));
    }
    req[location] = value;
    next();
  };
}

module.exports = { validate };
