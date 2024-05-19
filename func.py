from parliament import Context
from flask import Request
import json
import pprint
import sys
import base64
import os

from cloudevents.http import CloudEvent
from cloudevents.conversion import to_binary
from cloudevents.conversion import to_structured
from cloudevents.http import from_http

from neomodel import config
from neo4j import GraphDatabase

from neomodel import (config, StructuredNode, StringProperty, IntegerProperty,
	UniqueIdProperty, RelationshipTo, RelationshipFrom, Relationship, One, OneOrMore,
    DateTimeProperty)


neo4j_url = os.getenv("NEO4J_URL")
neo4j_username = os.getenv("NEO4J_USERNAME")
neo4j_password = os.getenv("NEO4J_PASSWORD")


config.DATABASE_URL = f"bolt://{neo4j_user}:{neo4j_password}@{neo4j_url}" 
config.DRIVER = GraphDatabase.driver(f"bolt://{neo4j_url}") 

class MindwmUser(StructuredNode):
    username = StringProperty(required = True)
    host = RelationshipTo('MindwmHost', 'HAS_MINDWM_HOST')

class MindwmHost(StructuredNode): 
    hostname = StringProperty(required = True)
    tmux = RelationshipTo('Tmux', 'HAS_TMUX')

class Tmux(StructuredNode):
    socket_path = StringProperty(required = True)
    session = RelationshipTo('TmuxSession', 'HAS_TMUX_SESSION')

class TmuxSession(StructuredNode):
    name = StringProperty(required = True)
    pane = RelationshipTo('TmuxPane', 'HAS_TMUX_PANE')

class TmuxPane(StructuredNode):
    pane_id = IntegerProperty(required = True)
    title = StringProperty()
    io_document = Relationship('IoDocument', 'HAS_IO_DOCUMENT')

class IoDocument(StructuredNode):
    uuid = StringProperty(unique_index=True, required = True)
    user_input = StringProperty(required = True)
    output = StringProperty(required = True)
    ps1 = StringProperty(required = True)
    time = DateTimeProperty(default_now = True)
    tmux_pane = Relationship('TmuxPane', 'HAS_IO_DOCUMENT')

# parse request body, json data or URL query parameters
def main(context: Context):
    """ 
    Function template
    The context parameter contains the Flask request object and any
    CloudEvent received with the request.
    """

    # Add your business logic here
    print("Received request")

    if 'request' in context.keys():
        pprint.pprint(context.request.headers)
        sys.stdout.flush()
        event = from_http(context.request.headers, context.request.data)
        pprint.pprint(event)
        sys.stdout.flush()

        source = event['source'].split(".")
        username = source[1]
        hostname = source[2]
        assert(source[3] == 'tmux')
        socket_path = str(base64.b64decode(source[4])).strip()
        pid = source[5]
        session_name = source[6]
        pane_id = int(source[7])

        user = MindwmUser.get_or_create({
                "username": username
              })[0]

        host = MindwmHost.get_or_create({
                "hostname": hostname 
             })[0]

        user.host.connect(host)

        tmux = Tmux.get_or_create({
                "socket_path": socket_path
            })[0]

        host.tmux.connect(tmux)

        tmux_session = TmuxSession.get_or_create({
                "name": session_name
            })[0]

        tmux.session.connect(tmux_session)

        tmux_pane = TmuxPane.get_or_create({
                "pane_id": pane_id
            })[0]

        tmux_session.pane.connect(tmux_pane)
        io_document = event.data['iodocument']

        io_document = IoDocument(
                    uuid = event['id'],
                    user_input = io_document['input'],
                    output = io_document['output'],
                    ps1 = io_document['ps1']
                ).save()

        tmux_pane.io_document.connect(io_document)
        io_document.tmux_pane.connect(tmux_pane)
        return "", 200
    else:
        print("Empty request", flush=True)
        return "{}", 200
