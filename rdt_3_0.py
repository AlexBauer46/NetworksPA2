import Network
import argparse
from time import sleep
import hashlib
import time


class Packet:
    ## the number of bytes used to store packet length
    seq_num_S_length = 10
    length_S_length = 10
    ##ADDED CODE
    pktTypeLen = 5
    ##/ADDED CODE
    ## length of md5 checksum in hex
    checksum_length = 32

    def __init__(self, seq_num, pktType, msg_S):  ##ADDED pktType
        self.seq_num = seq_num
        self.msg_S = msg_S
        self.pktType = pktType  ##ADDED

    @classmethod
    def from_byte_S(self, byte_S):
        #if Packet.corrupt(byte_S):
            #raise RuntimeError('Cannot initialize Packet: byte_S is corrupt')
        # extract the fields
        seq_num = int(byte_S[Packet.length_S_length: Packet.length_S_length + Packet.seq_num_S_length])
        pktType = int(byte_S[
                      Packet.length_S_length + Packet.seq_num_S_length: Packet.length_S_length + Packet.seq_num_S_length + Packet.pktTypeLen])
        msg_S = byte_S[Packet.length_S_length + Packet.seq_num_S_length + Packet.pktTypeLen + Packet.checksum_length:]
        return self(seq_num, pktType, msg_S)

    def get_byte_S(self):
        # convert sequence number of a byte field of seq_num_S_length bytes
        seq_num_S = str(self.seq_num).zfill(self.seq_num_S_length)
        ## convert pktType to a byte field of pktTypeLength bytes
        pktType_S = str(self.pktType).zfill(self.pktTypeLen)
        # convert length to a byte field of length_S_length bytes
        length_S = str(
            self.length_S_length + len(seq_num_S) + len(pktType_S) + self.checksum_length + len(self.msg_S)).zfill(
            self.length_S_length)
        # compute the checksum
        checksum = hashlib.md5((length_S + seq_num_S + pktType_S + self.msg_S).encode('utf-8'))
        checksum_S = checksum.hexdigest()
        # compile into a string
        return length_S + seq_num_S + pktType_S + checksum_S + self.msg_S

    @staticmethod
    def corrupt(byte_S):
        # extract the fields
        length_S = byte_S[0:Packet.length_S_length]
        seq_num_S = byte_S[Packet.length_S_length: Packet.length_S_length + Packet.seq_num_S_length]
        pktType_S = byte_S[
                    Packet.length_S_length + Packet.seq_num_S_length: Packet.length_S_length + Packet.seq_num_S_length + Packet.pktTypeLen]
        checksum_S = byte_S[
                     Packet.length_S_length + Packet.seq_num_S_length + Packet.pktTypeLen:
                     Packet.length_S_length + Packet.seq_num_S_length + Packet.pktTypeLen + Packet.checksum_length]
        msg_S = byte_S[Packet.length_S_length + Packet.seq_num_S_length + Packet.pktTypeLen + Packet.checksum_length:]

        # compute the checksum locally
        checksum = hashlib.md5(str(length_S + seq_num_S + pktType_S + msg_S).encode('utf-8'))
        computed_checksum_S = checksum.hexdigest()
        # and check if the same
        return checksum_S != computed_checksum_S


class RDT:
    ## latest sequence number used in a packet
    seq_num = 1
    ## buffer of bytes read from network
    byte_buffer = ''
    ## timeout for 3.0
    timeout = 0.5
    ## last seq_num received
    lastRec = seq_num-1

    def __init__(self, role_S, server_S, port):
        # use the passed in port and port+1 to set up unidirectional links between
        # RDT send and receive functions
        # cross the ports on the client and server to match net_snd to net_rcv
        if role_S == 'server':
            self.net_snd = Network.NetworkLayer(role_S, server_S, port)
            self.net_rcv = Network.NetworkLayer(role_S, server_S, port + 1)
        else:
            self.net_rcv = Network.NetworkLayer(role_S, server_S, port)
            self.net_snd = Network.NetworkLayer(role_S, server_S, port + 1)

    def disconnect(self):
        self.net_snd.disconnect()
        self.net_rcv.disconnect()

    def rdt_1_0_send(self, msg_S):
        p = Packet(self.seq_num, msg_S)
        self.seq_num += 1
        # !!! make sure to use net_snd link to udt_send and udt_receive in the RDT send function
        self.net_snd.udt_send(p.get_byte_S())

    def rdt_1_0_receive(self):
        ret_S = None
        # !!! make sure to use net_rcv link to udt_send and udt_receive the in RDT receive function
        byte_S = self.net_rcv.udt_receive()
        self.byte_buffer += byte_S
        # keep extracting packets - if reordered, could get more than one
        while True:
            # check if we have received enough bytes
            if (len(self.byte_buffer) < Packet.length_S_length):
                return ret_S  # not enough bytes to read packet length
            # extract length of packet
            length = int(self.byte_buffer[:Packet.length_S_length])
            if len(self.byte_buffer) < length:
                return ret_S  # not enough bytes to read the whole packet
            # create packet from buffer content and add to return string
            p = Packet.from_byte_S(self.byte_buffer[0:length])
            ret_S = p.msg_S if (ret_S is None) else ret_S + p.msg_S
            # remove the packet bytes from the buffer
            self.byte_buffer = self.byte_buffer[length:]

    # if this was the last packet, will return on the next iteration

    def rdt_2_1_send(self, pktType, msg_S):
        print('SENDING')
        p = Packet(self.seq_num, pktType, msg_S)
        ##self.seq_num += 1
        # !!! make sure to use net_snd link to udt_send and udt_receive in the RDT send function
        self.net_snd.udt_send(p.get_byte_S())
        if p.pktType == 0:  ##if sent packet was DATA type
            print('waiting for response')
            reading = True
            length = 9999999999999999999999999999
            while reading:
                byte_S = self.net_rcv.udt_receive()
                self.byte_buffer += byte_S
                if (len(self.byte_buffer) >= Packet.length_S_length):
                    length = int(self.byte_buffer[:Packet.length_S_length])
                if len(self.byte_buffer) >= length:
                    rec_S = self.byte_buffer[0:length]
                    self.byte_buffer = self.byte_buffer[length:]
                    reading = False

            if Packet.corrupt(rec_S):
                print('corrupt!')
                self.rdt_2_1_send(1, '')
                self.rdt_2_1_send(pktType, msg_S)
            else:
                recType = rec_S[
                          Packet.length_S_length + Packet.seq_num_S_length: Packet.length_S_length + Packet.seq_num_S_length + Packet.pktTypeLen]
                if recType == '00001':  ##ACK
                    print('ACK')
                    self.seq_num += 1
                else:  ##NAK
                    print('NAK')
                    self.rdt_2_1_send(pktType, msg_S)

    def rdt_2_1_receive(self):
        ret_S = None
        # !!! make sure to use net_rcv link to udt_send and udt_receive the in RDT receive function
        byte_S = self.net_rcv.udt_receive()
        #print('receiving')
        self.byte_buffer += byte_S
        #print(self.byte_buffer)
        # keep extracting packets - if reordered, could get more than one
        while True:
            # check if we have received enough bytes
            if (len(self.byte_buffer) < Packet.length_S_length):
                return ret_S  # not enough bytes to read packet length
            # extract length of packet
            length = int(self.byte_buffer[:Packet.length_S_length])
            if len(self.byte_buffer) < length:
                return ret_S  # not enough bytes to read the whole packet
            print('waiting for more bytes')
            # create packet from buffer content and add to return string
            if Packet.corrupt(self.byte_buffer[0:length]):
                print('received corrupt string')
                self.byte_buffer = self.byte_buffer[length:]
                length = ''
                return ret_S
            self.rdt_3_0_send(1, '')
            print('ack sent')
            p = Packet.from_byte_S(self.byte_buffer[0:length])
            ret_S = p.msg_S if (ret_S is None) else ret_S + p.msg_S
            # remove the packet bytes from the buffer
            self.byte_buffer = self.byte_buffer[length:]
        # if this was the last packet, will return on the next iteration

    def rdt_3_0_send(self, pktType, msg_S):
        print('SENDING')
        sendT = time.time()
        p = Packet(self.seq_num, pktType, msg_S)
        ##self.seq_num += 1
        # !!! make sure to use net_snd link to udt_send and udt_receive in the RDT send function
        self.net_snd.udt_send(p.get_byte_S())
        if p.pktType == 0:  ##if sent packet was DATA type
            print('waiting for response')
            reading = True
            length = 9999999999999999999999999999
            while reading:
                byte_S = self.net_rcv.udt_receive()
                self.byte_buffer += byte_S
                if (len(self.byte_buffer) >= Packet.length_S_length):
                    length = int(self.byte_buffer[:Packet.length_S_length])
                if len(self.byte_buffer) >= length:
                    rec_S = self.byte_buffer[0:length]
                    self.byte_buffer = self.byte_buffer[length:]
                    reading = False
                if sendT + self.timeout < time.time():
                    self.byte_buffer = ''
                    print('timed out')
                    self.net_snd.udt_send(p.get_byte_S())
                    sendT = time.time()

            if Packet.corrupt(rec_S):
                print('corrupt!')
            else:
                recType = rec_S[
                          Packet.length_S_length + Packet.seq_num_S_length: Packet.length_S_length + Packet.seq_num_S_length + Packet.pktTypeLen]
                if recType == '00001':  ##ACK
                    print('ACK')
                    self.seq_num += 1

    def rdt_3_0_receive(self):
        ret_S = None
        # !!! make sure to use net_rcv link to udt_send and udt_receive the in RDT receive function
        byte_S = self.net_rcv.udt_receive()
        # print('receiving')
        self.byte_buffer += byte_S
        # print(self.byte_buffer)
        # keep extracting packets - if reordered, could get more than one
        while True:
            # check if we have received enough bytes
            if (len(self.byte_buffer) < Packet.length_S_length):
                return ret_S  # not enough bytes to read packet length
            # extract length of packet
            length = int(self.byte_buffer[:Packet.length_S_length])
            if len(self.byte_buffer) < length:
                return ret_S  # not enough bytes to read the whole packet
            print('waiting for more bytes')
            # create packet from buffer content and add to return string
            if Packet.corrupt(self.byte_buffer[0:length]):
                print('received corrupt string')
                self.byte_buffer = self.byte_buffer[length:]
                return ret_S
            p = Packet.from_byte_S(self.byte_buffer[0:length])

            if p.seq_num <= self.lastRec:
                self.rdt_3_0_send(1, '')
                ret_S = p.msg_S if (ret_S is None) else ret_S + p.msg_S
                # remove the packet bytes from the buffer
                self.byte_buffer = self.byte_buffer[length:]
            elif p.seq_num > self.lastRec:
                self.lastRec = p.seq_num
                self.rdt_3_0_send(1, '')
                print('ack sent')
                ret_S = p.msg_S if (ret_S is None) else ret_S + p.msg_S
                # remove the packet bytes from the buffer
                self.byte_buffer = self.byte_buffer[length:]
        # if this was the last packet, will return on the next iteration


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='RDT implementation.')
    parser.add_argument('role', help='Role is either client or server.', choices=['client', 'server'])
    parser.add_argument('server', help='Server.')
    parser.add_argument('port', help='Port.', type=int)
    args = parser.parse_args()

    rdt = RDT(args.role, args.server, args.port)
    if args.role == 'client':
        rdt.rdt_2_1_send(0, 'MSG_FROM_CLIENT')
        sleep(2)
        print(rdt.rdt_2_1_receive())
        rdt.disconnect()


    else:
        sleep(1)
        print(rdt.rdt_2_1_receive())
        rdt.rdt_2_1_send(0, 'MSG_FROM_SERVER')
        rdt.disconnect()
