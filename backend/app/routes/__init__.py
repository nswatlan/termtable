"""HTTP layer. Each module is a Flask blueprint whose handlers only read the
request (path, query string, JSON body, session), call one service function
and shape the HTTP response.
"""
