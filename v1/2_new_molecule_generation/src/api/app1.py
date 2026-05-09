
from flask import Flask
# Instead of using this: from flask_restful import Api
# Use this:
from flask_restful_swagger_3 import Api, swagger, Resource

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_restful_swagger_3 import get_swagger_blueprint


app = Flask(__name__)
limiter = Limiter(
    app,
    key_func=get_remote_address
)

# Use the swagger Api class as you would use the flask restful class.
# It supports several (optional) parameters, these are the defaults:
api = Api(app)

from flask_restful_swagger_3 import Schema

class EmailModel(Schema):
    type = 'string'
    format = 'email'


class KeysModel(Schema):
    type = 'object'
    properties = {
        'name': {
            'type': 'string'
        }
    }


class UserModel(Schema):
    type = 'object'
    properties = {
        'id': {
            'type': 'integer',
            'format': 'int64',
        },
        'name': {
            'type': 'string'
        },
        'mail': EmailModel,
        'keys': KeysModel.array()
    }
    required = ['name']

class MyApi(Resource):

    decorators = [limiter.limit('20/day')]
    @swagger.tags(['user'])
    @swagger.reorder_with(UserModel, description="Returns a user")
    def get(self, userId):
        print("Hello I am in API")
        return {
            "id": userId,
            "name": "somename",
            "absc":"def"
        }


api.add_resource(MyApi, '/users/<int:userId>')

@app.route("/slow")
@limiter.limit("1 per day")
def slow():
    return "24"


@app.route("/fast")
def fast():
    return "42"


@app.route("/ping")
@limiter.exempt
def ping():
    return 'PONG'

#api = sg.docs(Api(app), apiVersion='1.0', swaggerVersion="3.0", api_spec_url='/docs')


if __name__ == "__main__":
    app.run(debug=True)
