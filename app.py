import http.server
import json
import logging
from pathlib import Path
import mimetypes
import socket
from threading import Thread
import urllib.parse
from urllib.parse import ParseResult
from datetime import datetime
from typing import Tuple, Dict
from http.server import HTTPServer, BaseHTTPRequestHandler

from jinja2 import Environment, FileSystemLoader, Template


BASE_DIRECTION: Path = Path()
SERVER_IP: str = '127.0.0.1'
OUTER_IP: str = '0.0.0.0'
PORT_FROM: int = 3000
PORT_TO: int = 5000
BUFFER_SIZE: int = 1024

env: Environment = Environment(loader=FileSystemLoader('templates'))


def send_to_server(file: bytes) -> None:
    client_socket: socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client_socket.sendto(file, (SERVER_IP, PORT_TO))
    client_socket.close()


class HTTPHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        body: bytes = self.rfile.read(int(self.headers['Content-Length']))
        send_to_server(body)
        self.send_response(302)
        self.send_header('Location', '/')
        self.end_headers()

    def do_GET(self):
        route: ParseResult = urllib.parse.urlparse(self.path)
        match route.path:
            case '/':
                self.send_html('index.html')
            case '/message':
                self.send_html('message.html')
            case '/blog':
                self.render_template('blog.html')
            case _:
                file: Path = BASE_DIRECTION/route.path[1:]
                if file.exists():
                    self.send_static(file)
                else:
                    self.send_html('error.html', 404)

        '''if route.path == '/':
            self.send_html('index.html')
        elif route.path == '/message':
            self.send_html('message.html')
        elif route.path == '/blog':
            self.send_html('blog.html')
        else:
            file = BASE_DIRECTION / route.path[1:]
            if file.exists():
                self.send_static(file)
            else:
                self.send_html('error.html', 404)'''

    def send_html(self, file_name: str, status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        with open(file_name, 'rb') as fr:
            self.wfile.write(fr.read())

    def send_static(self, file_name: Path) -> None:
        self.send_response(200)
        m_type: Tuple[str, str] = mimetypes.guess_type(file_name)
        if m_type[0]:
            self.send_header('Content-Type', m_type[0])
        else:
            self.send_header('Content_Type', 'text-plain')
        self.end_headers()
        with open(file_name, 'rb') as fr:
            self.wfile.write(fr.read())

    def render_template(self, file_name: str, status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        with open('for_blog.json', 'r', encoding='utf-8') as fr:
            blogs_data: list = json.load(fr)
        template: Template = env.get_template(file_name)
        html: str = template.render(blogs=blogs_data)
        self.wfile.write(html.encode())


def form_data(data: bytes) -> None:
    body: str = urllib.parse.unquote_plus(data.decode())
    try:
        after_parsing: Dict[str, str] = {key: value for key, value in [el.split('=') for el in body.split('&')]}
        data: Dict[str, Dict[str]] = {datetime.now().strftime('%Y-%m-%d %H:%M:%S'): after_parsing}
        with open('storage/data.json', 'r', encoding='utf-8') as fr:
            total_data: Dict[str, Dict[str]] = json.load(fr)
        total_data.update(data)
        with open('storage/data.json', 'w', encoding='utf-8') as fw:
            json.dump(total_data, fw, ensure_ascii=False, indent=4)
    except ValueError as error:
        logging.error(f'Field parse data {body} with error: {error}')
    except OSError as error:
        logging.error(f'Field write data {body} with error: {error}')


def run(server_class: http.server, handler_class: HTTPHandler) -> None:
    server_address: Tuple[str, int] = (OUTER_IP, PORT_FROM)
    http_server: HTTPServer = server_class(server_address, handler_class)
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        http_server.server_close()


def run_socket_server(ip_address: str, port: int) -> None:
    server_socket: socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.bind((ip_address, port))
    try:
        while True:
            data: bytes = server_socket.recv(BUFFER_SIZE)
            form_data(data)
    except (KeyboardInterrupt, ValueError) as error:
        logging.info(f'socket server stopped: {error}')
    finally:
        server_socket.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(threadName)s - %(message)s')

    STORAGE_DIRECTION: Path = Path().joinpath('storage')
    FILE_STORAGE: Path = STORAGE_DIRECTION/'data.json'
    if not FILE_STORAGE.exists():
        with open(FILE_STORAGE, 'w', encoding='utf-8') as fd:
            json.dump({}, fd, ensure_ascii=False)

    thread_http_server: Thread = Thread(target=run, args=(HTTPServer, HTTPHandler))
    thread_http_server.start()
    thread_socket_server: Thread = Thread(target=run_socket_server, args=(SERVER_IP, PORT_TO))
    thread_socket_server.start()
