# Copyright (c) 2012, Christopher Gamble
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the Christopher Gamble nor the names of its 
#      contributors may be used to endorse or promote products derived 
#      from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED 
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
# OF THE POSSIBILITY OF SUCH DAMAGE.

try:
    from twisted.web.websockets import WebSocketsResource
except ImportError:
    from txsockjs.websockets import WebSocketsResource

from zope.interface import directlyProvides, providedBy
from twisted.internet.protocol import Protocol
from twisted.protocols.policies import WrappingFactory, ProtocolWrapper
from twisted.web.server import NOT_DONE_YET
from txsockjs.oldwebsockets import OldWebSocketsResource
import json

class JsonProtocol(ProtocolWrapper):
    def makeConnection(self, transport):
        directlyProvides(self, providedBy(transport))
        Protocol.makeConnection(self, transport)
        self.transport.write("o")
        self.factory.registerProtocol(self)
        self.wrappedProtocol.makeConnection(self)
    
    def write(self, data):
        self.writeSequence([data])
    
    def writeSequence(self, data):
        self.transport.write("a{}".format(json.dumps(data)))
    
    def loseConnection(self):
        self.transport.write('c[3000,"Go away!"]')
        ProtocolWrapper.loseConnection(self)
    
    def dataReceived(self, data):
        if not data:
            return
        try:
            data = json.loads(data)
            for d in data:
                ProtocolWrapper.dataReceived(self, d)
        except ValueError:
            self.transport.loseConnection()

class JsonFactory(WrappingFactory):
    protocol = JsonProtocol

class RawWebSocket(WebSocketsResource, OldWebSocketsResource):
    def __init__(self):
        self._factory = None
    
    def _makeFactory(self):
        WebSocketsResource.__init__(self, self.parent._factory) 
        OldWebSocketsResource.__init__(self, self.parent._factory) 
    
    def render(self, request):
        # Get around .parent limitation
        if self._factory is None:
            self._makeFactory()
        # Override handling of invalid methods, returning 400 makes SockJS mad
        if request.method != 'GET':
            request.setResponseCode(405)
            request.defaultContentType = None # SockJS wants this gone
            request.setHeader('Allow','GET')
            return ""
        # Override handling of lack of headers, again SockJS requires non-RFC stuff
        upgrade = request.getHeader("Upgrade")
        if upgrade is None or "websocket" not in upgrade.lower():
            request.setResponseCode(400)
            return 'Can "Upgrade" only to "WebSocket".'
        connection = request.getHeader("Connection")
        if connection is None or "upgrade" not in connection.lower():
            request.setResponseCode(400)
            return '"Connection" must be "Upgrade".'
        # Defer to inherited methods
        ret = WebSocketsResource.render(self, request) # For RFC versions of websockets
        if ret is NOT_DONE_YET:
            return ret
        return OldWebSocketsResource.render(self, request) # For non-RFC versions of websockets

class WebSocket(RawWebSocket):
    def _makeFactory(self):
        f = JsonFactory(self.parent._factory)
        WebSocketsResource.__init__(self, f)
        OldWebSocketsResource.__init__(self, f)
