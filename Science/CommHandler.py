"""
TCP/UDP Communications Handler.

Written by Jaden Bottemiller in January 2017
EE Team of Husky Robotics
Questions/Comments? Email: jadenjb@uw.edu
(Untested as of 2/6/2017)

"""
import socket
from threading import Thread
from Error import Error


class CommHandler:

    SOCKET = None
    BYTE_BUFFER_SIZE = 1024
    TCP_SEND_TIMEOUT = 300

    def __init__(self, internalIP, receivePort):
        self._internalIP = internalIP
        self._receivePort = receivePort
        self._packets = []
        self.SOCKET = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.SOCKET.bind((self._internalIP, self._receivePort))
        self._messages = []
        self._continue = True
        self._receiving = False

    @classmethod
    def sendAsyncPacket(cls, packet):
        _sendThread = Thread(target=packet.send)
        _sendThread.start()

    def addCyclePacket(self, packet):
        self._packets += [packet]

    def sendAll(self):
        _sendThread = Thread(target=self._sendPackets)
        _sendThread.start()

    def _sendPackets(self):
        while len(self._packets) > 0:
            self._packets[0].send()
            del self._packets[0]

    def stopComms(self):
        self._continue = False

    def getReceivingStatus(self):
        return self._receiving

    # Returns messages and deletes them from the waiting queue
    def getMessages(self):
        temp = self._messages
        self._messages = []
        return temp

    # Meant to be threaded on system
    # Otherwise there will be an infinite loop
    def receiveMessagesOnThread(self):
        self._continue = True
        try:
            while self._continue:
                self.SOCKET.listen(1)
                client, clientAddr = self.SOCKET.accept()
                self._receiving = True
                data = client.recv(self.BYTE_BUFFER_SIZE)
                self._receiving = False
                self._messages += [Message(data, clientAddr)]
        except socket.error:
            Error.throw(0x00FF)  # Need to add actual error code here once documented.


class Message:

    def __init__(self, data, fromAddr):
        self.DATA = data
        self.fromAddr = fromAddr
        # parse ID from given data
        self.ID = int(data[31:39])