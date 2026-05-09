from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_restful import Api, Resource

from flasgger import Swagger
from flask_restful_swagger import swagger
from flasgger.utils import swag_from

app = Flask(__name__)
limiter = Limiter(
    app,
    key_func=get_remote_address
)

api = swagger.docs(Api(app), apiVersion='1.0', swaggerVersion="2.0", api_spec_url='/docs')


class MyApi(Resource):
    decorators = [limiter.limit('20/day')]

    def get(self, zip):
        return {
            "Response": 200,
            "Data": zip
        }


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


api.add_resource(MyApi, '/weather/<string:zip>')


app.run()
