# -*- coding: utf-8 -*-

"""
Fetch a list of channels from TVHeadend
"""

import logging
import requests
import socket
import sys
from requests.auth import HTTPDigestAuth
from urllib.parse import urlparse

def tvh_get_channels(host, port=9981, username='', password=''):
  channels = []

  try:
    host = host if host.startswith('http://') or host.startswith('https://') else '//' + host
    url_object = urlparse(host, scheme='http')
    if url_object.port:
      port = url_object.port
  except ValueError:
    port = 9981

  request_uri = '{:s}://{:s}:{:d}{:s}/api/channel/list'.format(url_object.scheme, url_object.hostname, port, url_object.path)
  try:
    r = requests.get(request_uri, auth=(username, password), timeout=10)
  except requests.exceptions.RequestException as e:
    warning('Connection to Tvheadend URI {:s} failed: {:s}'.format(request_uri, str(e)))
    sys.exit(1)

  if r.status_code == 401:
    # Retry with HTTP digest authentication
    r = requests.get(request_uri, auth=HTTPDigestAuth(username, password))
  if r.status_code != 200:
    error_msg = 'Connection to Tvheadend URI {:s} failed with status {:d}.'.format(request_uri, r.status_code)
    warning(error_msg)
    raise Exception(error_msg)
  data = r.json()
  if 'entries' in data:
    for channel in data['entries']:
      if 'val' in channel:
        channels.append(channel['val'])
  return channels

def warning(msg):
  logging.warning(msg)

class TVHXMLTVSocket(object):
  def __init__(self, path):
    self.path = path
    self.sock = False
  def __enter__(self):
    return self
  def __exit__(self, type, value, traceback):
    if(self.sock):
      self.sock.close()
  def send(self, data):
    self.sock = socket.socket(socket.AF_UNIX)
    self.sock.connect(self.path)
    self.sock.sendall(data)
    self.sock.close()
