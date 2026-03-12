from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from models.user import User
from models.contact import Contact
from models.message import Message
from models.call_log import CallLog
from models.group import Group, GroupMember
from models.calendar_event import CalendarEvent
