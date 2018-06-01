import os
import redis
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.wsgi import SharedDataMiddleware
from werkzeug.utils import redirect
from jinja2 import Environment, FileSystemLoader
from datetime import datetime


def is_valid_data(creator, board_name):
    return True

def base36_encode(number):
    assert number >= 0, 'positive integer required'
    if number == 0:
        return '0'
    base36 = []
    while number != 0:
        number, i = divmod(number, 36)
        base36.append('0123456789abcdefghijklmnopqrstuvwxyz'[i])
        return ''.join(reversed(base36))


class Board(object):
    def __init__(self, config):
        self.redis = redis.Redis(config['redis_host'], config['redis_port'], decode_responses=True)
        template_path = os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path),
                                     autoescape=True)
        self.url_map = Map([
            Rule('/', endpoint='new_boards'),
            Rule('/<board_id>', endpoint='board_details'),
            Rule('/<board_id>+', endpoint='add_comment_to_board')
        ])

    def render_template(self, template_name, **context):
        t = self.jinja_env.get_template(template_name)
        return Response(t.render(context), mimetype='text/html')

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, 'on_' + endpoint)(request, **values)
        except HTTPException as e:
            return e

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)

    def on_new_boards(self, request):
        error = None
        if request.method == 'POST':
            creator = request.form['creator']
            board_name = request.form['board_name']
            if not is_valid_data(creator, board_name):
                error = 'Please enter a valid data'
            else:
                board_id = self.insert_new_desk(creator, board_name)
                return redirect('/%s' % board_id, error=error)
                
        boards = self.redis.keys('board:*')
        boards_list = []
        for board in boards:
            board_name = self.redis.get(board)
            creator = self.redis.get('creator:' + board)
            board_id = board.split(':')[1]
            boards_list.append({'id': board_id, 'name': board_name, "creator": creator})
        return self.render_template('boards.html', boards_list=boards_list, error=error)
    
    def on_board_details(self, request, board_id):
        print(board_id)
        board_name = self.redis.get('board:' + board_id)
        creator = self.redis.get('creator:board:' + board_id)
        if board_name is None:
            raise NotFound()
        print(board_name)
        comments =
        return self.render_template('boards.html',
                                    board_name=board_name,
                                    creator=creator,
                                    comments=comments)

    def insert_new_desk(self, creator, board_name):
        board_id = str(self.redis.incr('last-desk-id'))
        
        self.redis.set('board:' + board_id, board_name)
        self.redis.set('creator:board:' + board_id, creator)
        self.redis.set('creation_date:board:' + board_id, datetime.now())
        
        return board_id


def create_app(redis_host='localhost', redis_port=6379, with_static=True):
    app = Board({
        'redis_host': redis_host,
        'redis_port': redis_port
    })
    if with_static:
        app.wsgi_app = SharedDataMiddleware(app.wsgi_app, {
            '/static': os.path.join(os.path.dirname(__file__), 'static')
        })
    return app


if __name__ == '__main__':
    from werkzeug.serving import run_simple
    app = create_app()
    run_simple('127.0.0.1', 5000, app, use_debugger=True, use_reloader=True)
