from typing import Union
from flask import Flask, jsonify, request
from flask.views import MethodView
from sqlalchemy import Column, Integer, String, DateTime, func, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.exc import IntegrityError
import atexit
import pydantic
from typing import Optional


app = Flask('HomeWork')

DSN = 'postgresql://postgres:postgres@127.0.0.1:5432/flask_hw'
engine = create_engine(DSN)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class HttpError(Exception):
    def __init__(self, status_code: int, message: Union[str, dict, list]):
        self.status_code = status_code
        self.message = message


@app.errorhandler(HttpError)
def http_error_handler(err: HttpError):
    response = jsonify({
        'status': 'error',
        'message': err.message
    })
    response.status_code = err.status_code
    return response


class Adt(Base):
    __tablename__ = 'adt'
    id = Column(Integer, primary_key=True)
    owner = Column(String(120), unique=False, nullable=False)
    header = Column(String(120), nullable=False)
    description = Column(String, nullable=False)
    creation_time = Column(DateTime, server_default=func.now())


Base.metadata.create_all(engine)


def on_exit():
    engine.dispose()


atexit.register(on_exit)


class CreateAdtSchema(pydantic.BaseModel):
    owner: str
    header: str
    description: str

    @pydantic.validator('description')
    def short_description(cls, value: str):
        if len(value) <= 8:
            raise ValueError('Description is too short')
        return value


class UpdateAdtSchema(pydantic.BaseModel):
    owner: Optional[str]
    header: Optional[str]
    description: Optional[str]

    @pydantic.validator('description')
    def short_description(cls, value: str):
        if len(value) <= 8:
            raise ValueError('Description is too short')
        return value


def validate(Schema, data: dict):
    try:
        data_validated = Schema(**data).dict(exclude_none=True)
    except pydantic.ValidationError as er:
        raise HttpError(400, er.errors())
    return data_validated


def get_adt(adt_id: int, session: Session) -> Adt:
    adt = session.query(Adt).get(adt_id)
    if adt is None:
        raise HttpError(404, 'adt_not_found')
    return adt


class AdtView(MethodView):

    def get(self, adt_id: int):
        with Session() as session:
            adt = get_adt(adt_id, session)
        return jsonify({'owner': adt.owner, 'header': adt.header, 'description': adt.description})

    def post(self):
        json_data = validate(CreateAdtSchema, request.json)
        with Session() as session:
            new_adt = Adt(**json_data)
            try:
                session.add(new_adt)
                session.commit()
            except IntegrityError:
                raise HttpError(400, 'something_wrong')

            return jsonify({'status': 'success', 'id': new_adt.id})

    def patch(self, adt_id: int):
        json_data = validate(UpdateAdtSchema, request.json)
        with Session() as session:
            adt = get_adt(adt_id, session)
            for key, value in json_data.items():
                setattr(adt, key, value)
            session.add(adt)
            session.commit()
        return jsonify({'status': 'success'})

    def delete(self, adt_id: int):
        with Session() as session:
            adt = get_adt(adt_id, session)
            session.delete(adt)
            session.commit()
        return jsonify({'status': 'success'})


app.add_url_rule('/adt/', methods=['POST'], view_func=AdtView.as_view('create_adt'))
app.add_url_rule('/adt/<int:adt_id>', methods=['GET', 'PATCH', 'DELETE'], view_func=AdtView.as_view('get_adt'))
app.run()
