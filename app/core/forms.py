from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, PasswordField, IntegerField, BooleanField, SelectField
from wtforms.validators import DataRequired, URL, Length, Email, EqualTo, NumberRange , Optional, Regexp

class UrlSubmit(FlaskForm):
    url = StringField('Url',validators=[DataRequired(),URL()])
    submit = SubmitField('Submit Url')

class PromptForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    template = TextAreaField('Template', validators=[DataRequired()])
    submit = SubmitField('Save Changes')

class SetupProfileForm(FlaskForm):
    full_name = StringField('Name',validators=[DataRequired()])
    interests_description = TextAreaField('Interests Description', validators=[DataRequired()])
    openai_api_key = TextAreaField('Open AI API key')
    submit = SubmitField('Save Changes')

class ArticleCompareForm(FlaskForm):
    article_url = StringField('Article URL', validators=[DataRequired(), URL()])
    submit = SubmitField('Compare with Profile')

class LoginForm(FlaskForm):
    email = StringField('Email',validators=[DataRequired(),Email()])
    password = PasswordField('Password',validators=[DataRequired()])
    submit = SubmitField('Login')

class RegistrationForm(FlaskForm):
    email = StringField('Email',validators=[DataRequired(),Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Register')

class SettingsForm(FlaskForm):
    openai_api_key = StringField('OpenAI API Key', validators=[DataRequired()])
    submit = SubmitField('Update Settings')

class ScheduleForm(FlaskForm):
    url = StringField('URL', validators=[DataRequired(), URL(message="The URL was invalid. Make sure to include https:// at the beginning.")])
    minutes = IntegerField('Minutes between runs', 
                          validators=[DataRequired(), NumberRange(min=1, max=1440)],  # max 24 hours
                          default=60)
    submit = SubmitField('Schedule Task')

class ProfileForm(FlaskForm):
    interests_description = TextAreaField('Interests Description', validators=[DataRequired()])
    submit = SubmitField('Update Profile')

class CreatePromptForm(FlaskForm):
    name = StringField('Prompt Name', validators=[DataRequired()])
    template = TextAreaField('Prompt Template', validators=[DataRequired()])
    type = SelectField('Prompt Type', choices=[('1', 'Article'), ('2', 'Article and Deep Research'), ('3', 'Group')])
    deep_research_prompt = TextAreaField('Deep Research Prompt')
    submit = SubmitField('Create Prompt')

class EditPromptForm(FlaskForm):
    name = StringField('Prompt Name', validators=[DataRequired()])
    template = TextAreaField('Prompt Template', validators=[DataRequired()])
    deep_research_prompt = TextAreaField('Deep Research Prompt')
    active = BooleanField('Active')
    submit = SubmitField('Save Changes')


class CreateGroupForm(FlaskForm):
    name = StringField('Group Name', validators=[DataRequired()])
    description = TextAreaField('Group Description')
    prompt_id = SelectField('Prompt', choices=[])
    submit = SubmitField('Create Group')

class EditGroupForm(FlaskForm):
    name = StringField('Group Name', validators=[DataRequired()])
    description = TextAreaField('Group Description')
    prompt_id = SelectField('Prompt', choices=[])
    submit = SubmitField('Save Changes')


