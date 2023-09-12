# Backend Flask Python

This project contains source code for web applications backend developed in flask framework.

Full project can be found at https://www.amdavadistreetz.com/products/

There are several different routes:

- addons - A blueprint that defines addons routes for the application. Spporting Add, Delete, Update and Retrieve addons from AWS RDS Postgres.
- customization - A blueprint that defines analytics routes for the application. Spporting Add, Delete, Update and Retrieve customizations from AWS RDS Postgres.
- products - A blueprint that defines analytics routes for the application. Spporting Add, Delete, Update and Retrieve products from AWS RDS Postgres.
- categories - A blueprint that defines analytics routes for the application. Spporting Add, Delete, Update and Retrieve categories from AWS RDS Postgres.
- users - A blueprint that defines analytics routes for the application. Spporting Register, Login, ResetPassword, Store address, Store payments etc. for users from AWS RDS Postgres.
- analytics - A blueprint that defines analytics routes for the application.

## Users Routes

Resgister users routes supports hashing password with help of bcrypt library. This ensures that users passowords are never read by another user.

Login routes implements security for burte forcing by freezing accoutns of the user who exceeds the maximum login attempts. user is forced to reset password then after with help of a token received on email.

Reset password routes is used to reset password from users or to unfreeze the user accoutn.

Store address and store payments route implements strict authentication bearer protection. The request needs to have a auth token to processed.

Loyalty route is used to add loyalty points to users and is also protetcted by strict auth bearer.

## Admin Routes

addons, customization, products, caregories, analytics routes are mostly admin only routes. Only get is public route rest of them are protected by auth token.

They all provide routes to be able to Add, Delete, Update and change instock status of the given variable.

## Deployment CI/CD

To deploy the backend activate venv and run `zappa update`

The api is deployed on Lambda on AWS to take advantage of the serverless infrastructure. Lambda is scallable, cheap and easy to deploy.

We use Zappa to deploy the flask app with ease to aws lambda

## TO-DO

- [ ] Protect Admin routes