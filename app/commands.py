# commands.py
import click
from flask.cli import with_appcontext
from app import db
from app.models.user import User

@click.command('create-admin')
@click.argument('username')
@click.argument('email')
@click.argument('password')
@with_appcontext
def create_admin(username, email, password):
    """Create an admin user"""
    user = User(username=username, email=email, is_admin=True)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    click.echo(f'Created admin user: {username}')

# В __init__.py добавить:
def register_commands(app):
    app.cli.add_command(create_admin)