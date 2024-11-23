from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models.user import User


class RegistrationForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[
        DataRequired(message="Это поле обязательно"),
        Length(min=3, max=64, message="Имя пользователя должно быть от 3 до 64 символов")
    ])

    email = StringField('Email', validators=[
        DataRequired(message="Это поле обязательно"),
        Email(message="Введите корректный email адрес"),
        Length(max=120, message="Email не может быть длиннее 120 символов")
    ])

    password = PasswordField('Пароль', validators=[
        DataRequired(message="Это поле обязательно"),
        Length(min=6, message="Пароль должен содержать минимум 6 символов")
    ])

    password2 = PasswordField('Подтвердите пароль', validators=[
        DataRequired(message="Это поле обязательно"),
        EqualTo('password', message='Пароли должны совпадать')
    ])

    submit = SubmitField('Зарегистрироваться')

    def validate_username(self, field):
        user = User.query.filter_by(username=field.data).first()
        if user:
            raise ValidationError('Это имя пользователя уже занято')

    def validate_email(self, field):
        user = User.query.filter_by(email=field.data).first()
        if user:
            raise ValidationError('Этот email уже зарегистрирован')


class LoginForm(FlaskForm):
    username = StringField('Имя пользователя или Email', validators=[
        DataRequired(message="Это поле обязательно")
    ])
    password = PasswordField('Пароль', validators=[
        DataRequired(message="Это поле обязательно")
    ])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')