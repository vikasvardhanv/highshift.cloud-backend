const expressSwagger = require('express-swagger-generator');

module.exports = (app) => {
  const expressSwaggerGen = expressSwagger(app);

  const options = {
    swaggerDefinition: {
      info: {
        description: 'API docs for the Social OAuth Backend',
        title: 'Social OAuth Backend',
        version: '1.0.0',
      },
      host: (process.env.BASE_URL || 'http://localhost:3000').replace(/^https?:\/\//, ''),
      basePath: '/',
      produces: ['application/json'],
      schemes: ['http', 'https'],
      securityDefinitions: {
        ApiKeyAuth: {
          type: 'apiKey',
          in: 'header',
          name: 'X-API-Key'
        }
      }
    },
    basedir: __dirname,
    files: ['./routes/*.js', './controllers/*.js'],
  };

  expressSwaggerGen(options);
};
