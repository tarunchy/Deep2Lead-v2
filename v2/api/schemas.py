from marshmallow import Schema, fields, validate, ValidationError, EXCLUDE


class GenerateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    amino_acid_seq = fields.Str(load_default="")
    smile = fields.Str(required=True, validate=validate.Length(min=2))
    noise = fields.Float(load_default=0.5, validate=validate.Range(min=0.0, max=1.0))
    num_candidates = fields.Int(load_default=10, validate=validate.Range(min=1, max=50))
    target_id = fields.Str(load_default=None)
    pdb_id = fields.Str(load_default=None)
    target_name = fields.Str(load_default=None)
    uniprot_id = fields.Str(load_default=None)
    mode = fields.Str(load_default="2d", validate=validate.OneOf(["2d", "3d"]))


class ExperimentUpdateSchema(Schema):
    title = fields.Str(validate=validate.Length(max=256))
    hypothesis = fields.Str()


class CommentSchema(Schema):
    body = fields.Str(required=True, validate=validate.Length(min=1, max=2000))
    tag = fields.Str(
        validate=validate.OneOf(["question", "suggestion", "correction", "praise"]),
        load_default=None,
    )
    parent_id = fields.UUID(load_default=None)


class CreateUserSchema(Schema):
    username = fields.Str(required=True, validate=validate.Length(min=3, max=64))
    display_name = fields.Str(validate=validate.Length(max=128))
    email = fields.Email()
    password = fields.Str(required=True, validate=validate.Length(min=6))
    cohort = fields.Str(validate=validate.Length(max=64))
    role = fields.Str(
        load_default="student",
        validate=validate.OneOf(["student", "admin"]),
    )


class UpdateUserSchema(Schema):
    is_active = fields.Bool()
    role = fields.Str(validate=validate.OneOf(["student", "admin"]))
    cohort = fields.Str(validate=validate.Length(max=64))
    display_name = fields.Str(validate=validate.Length(max=128))
