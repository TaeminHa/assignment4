##
## Python version of:
##
## ****************************************************************************
## ALTERNATING BIT AND GO-BACK-N NETWORK SIMULATOR: VERSION 1.1  J.F.Kurose
##
## Network properties/assumptions:
##   - one-way network delay averages 5.0 time units (longer if there
##     are other messages in the channel for GBN), but can be larger
##   - packets can be corrupted (either the header or the data portion)
##     or lost, according to user-defined probabilities
##   - packets will be delivered in the order in which they were sent
##     (although some can be lost).
## ****************************************************************************
##
## Modified by:
## Jeongyoon Moon <jeongyoonm@utexas.edu>
## University of Texas at Austin
## March 2024
##
## Python version by:
## Eric Eide <eeide@cs.utah.edu>
## University of Utah
## March 2022
##
## Run `python3 <thisfile.py> -h` in a terminal window to see the various
## parameters that you can set for a run of this simulator.
##
## This program defines a variable `TRACE` that you can use to conditionally
## print messages from your SndTransport and RcvTransport methods.  For example:
##
##   if TRACE>0:
##       print('A very important event just happened!')
##
## The value of `TRACE` is set by the `-v` command line option.  The default
## value of `TRACE` is 0 (meaning "no tracing").
##

import argparse
from copy import deepcopy
from enum import Enum, auto
import random
import sys
import time
import transport.init_sim as sim

###############################################################################

## ************************* BASIC DATA STRUCTURES ****************************
##
## STUDENTS: Do not modify these definitions.
##
## ****************************************************************************

# A Msg is the data unit passed from layer 5 (done by the provided code) 
# to layer 4 (your code).  It contains the data (bytes) to be delivered to layer 5
# via your transport-level protocol entities.

class Msg:
    MSG_SIZE = 20

    def __init__(self, data):
        self.data = data                # type: bytes[MSG_SIZE]

    def __str__(self):
        return 'Msg(data=%s)' % (self.data)

# A Pkt is the data unit passed from layer 4 (your code) to layer 3
# (handled by the provided code). Note the pre-defined packet structure, 
# which you must follow.

class Pkt:
    def __init__(self, seqnum:int, acknum:int, checksum:int, payload:bytes):
        self.seqnum = seqnum            # type: integer
        self.acknum = acknum            # type: integer
        self.checksum = checksum        # type: integer
        self.payload = payload          # type: bytes[Msg.MSG_SIZE]

    def __str__(self):
        return ('Pkt(seqnum=%s, acknum=%s, checksum=%s, payload=%s)'
                % (self.seqnum, self.acknum, self.checksum, self.payload))

###############################################################################

## ***************** TASKS: COMPLETE THE CODE BELOW **************************
##
## The code blocks you have to implement are marked as TODO
##
## NOTICE: When you implement these methods, use instance variables only!
## I.e., variables that you access through `self' like `self.x`.  Do NOT use
## global variables (a.k.a. module-scoped variables) or class variables.
##
## The reason for this restriction is the autograder, which may run several
## simulations within a single Python process.  For each simulation, the
## autograder will create a new instance of SndTransport and a new instance of
## RcvTransport.  If you use global variables and/or class variables in your
## implmentations of SndTransport and RcvTransport, then your code may not work properly
## when run by the autograder, and you may LOSE POINTS!
## ****************************************************************************

def calc_checksum(pkt:Pkt):
    # TODO: Write a function that calculates a checksum given a packet.
    
    checksum = 0

    for i in range(0, len(pkt.payload), 2):
        bit16 = pkt.payload[i] + (pkt.payload[i + 1] << 8)
        checksum += bit16

        if checksum & 0xFFFF0000:
            checksum &= 0xFFFF
            checksum += 1

    checksum += pkt.seqnum
    checksum += pkt.acknum

    return ~(checksum & 0xFFFF)

# SndTransport: a sender transport layer (layer 4)
class SndTransport:
    # The following method will be called once (only) before any other
    # SndTransport methods are called.  You can use it to do any initialization.
    #
    # seqnum_limit is "the number of distinct seqnum values that your protocol
    # may use."  The seqnums and acknums in all layer3 Pkts must be between
    # zero and seqnum_limit-1, inclusive.  E.g., if seqnum_limit is 16, then
    # all seqnums must be in the range 0-15.
    def __init__(self, seqnum_limit):
        # TODO: initalize the sender's states
        self.seqnum_limit = seqnum_limit

        # should be between [0, seqnum_limit - 1] 
        # basically stands for last successfully sent seq number
        # acknum represents the last received acknum, which should always be seqnum
        # is acknum != seqnum, then the last message wasn't ackknowledged;
        self.seqnum = 0
        self.acknum = 0

        # stands for the most recently attempted (possibly failed) sequence number
        # this field should always be last successfully sent seq number + 1
        self.cur_seqnum = 1

        # also stands for most recently attempted message
        # keep track for retransmitting purposes
        self.message = None

        
    # Called from layer 5, passed the data to be sent to other side.
    # The argument `message` is a Msg containing the data to be sent.
    def send(self, message):
        # TODO: Create a packet from the message and pass it to layer 3. 
        # This method also has to check # of in-flight packets and 
        # start a timer after sending the packet.
        # Refer to the assignment webpage for the core logic.

        # create a packet from the message
        pkt = Pkt(seqnum = self.cur_seqnum, acknum = self.acknum, checksum = 0, payload = message.data)
        # set checksum
        pkt.checksum = calc_checksum(pkt)

        # check if there's any unacknowledged packets; Refer to __init__()
        # this basically makes sure that there's only 1 outstanding packet
        if self.acknum == self.seqnum:
            self.message = message
            # print("SENDER: Sending " + str(pkt.payload) + " " + str(pkt.seqnum) + " " + str(self.seqnum) + " " + str(self.acknum))
            to_layer3(self, pkt)
            start_timer(self, 10.0)
        # else:
        #     print("SENDER: ERROR: THERE CAN ONLY BE 1 OUTSTANDING PACKET")
        #     exit()

    # Called from layer 3, when a packet arrives for layer 4 at SndTransport.
    # The argument `packet` is a Pkt containing the newly arrived packet.
    def recv(self, pkt):
        # TODO: Check the packet if it is corrupted or unexpected
        # and pass/discard the packet to layer 5 based on them.
        # Refer to the assignment webpage for the core logic.
        
        correct_checksum = pkt.checksum == calc_checksum(pkt)
        # check for NACK and actual acknum match
        correct_acknum = pkt.payload != b'                    ' and self.cur_seqnum == pkt.acknum
        
        # pkt must be an ack packet since it's unidirectional
        # check the checksum field for corruption
        # if any of the fields fail, we DO NOT have to retransmit and just ignore; 
        # this will be handled by the timeout
        # if not correct_checksum or not correct_acknum:
        #     if not correct_checksum:
        #         print("SENDER: ERROR: Corrupted Packet; Checksum Mismatch")
        #     if not correct_acknum:
        #         print("SENDER: ERROR: Unexpected ACK; Wanted: " + str(self.cur_seqnum) + " Received: " + str(pkt.acknum))

        # if the ack packet is fine, then we send it over to layer 5
        # and update SENDER metadata
        if correct_checksum and correct_acknum:
            # print("SENDER: Received ACK for " + str(pkt.payload))
            message = Msg(pkt.payload)

            self.seqnum = self.cur_seqnum
            self.acknum = self.seqnum
            self.cur_seqnum = (self.cur_seqnum + 1) % self.seqnum_limit
            stop_timer(self)
            
    # Called when the sender's timer goes off.
    def timer_interrupt(self):
        # TODO: handle retransmission when the timer expires
        # Refer to the assignment webpage for the core logic.
        # print("SENDER: Timer Expired; Retransmit " + str(self.message))
        self.send(self.message)

# RcvTransport: a receiver transport layer (layer 4)
class RcvTransport:
    # The following method will be called once (only) before any other
    # RcvTransport methods are called.  You can use it to do any initialization.
    #
    # See comment above `SndTransport.__init__` for the meaning of seqnum_limit.
    def __init__(self, seqnum_limit):
        # TODO: initalize the receiver's states
        self.seqnum_limit = seqnum_limit

        # should be between [0, seqnum_limit - 1] 
        # basically stands for the seqnum we're expecting to receive from the Sender
        # acknum represents the last ACK we sent; This accounts for possible loss of ACK message

        # if last_acked == incoming seq_num, that means there was a loss in ACK and it's a duplicate
        self.seqnum = 1
        self.last_acked = 0
        self.message = None

    # Called from layer 3, when a packet arrives for layer 4 at RcvTransport.
    # The argument `packet` is a Pkt containing the newly arrived packet.
    def recv(self, packet):
        
        # and pass/discard the packet to layer 5 based on them.
        # Plus, send an ACK message based on the validity of the packet.
        # Refer to the assignment webpage for the core logic.

        # TODO: Check the packet if it is corrupted or unexpected
        expected = packet.seqnum == self.seqnum or packet.seqnum == self.last_acked
        correct_checksum = packet.checksum == calc_checksum(packet)

        # print("RECEIVER: Received Packet " + str(packet.payload) + " " + str(self.seqnum) + " " + str(self.last_acked))
        
        if expected and correct_checksum:
            # previous ack might've been lost, so we need to detect duplicate packet
            # if packet.seqnum == self.last_acked:
            #     # don't send it to layer_5 bc this is a duplicate
            #     print("RECEIVER: Duplicate Packet; Previous ACK failed")
            if packet.seqnum != self.last_acked:
                # 1st time seeing this packet, and seqnum and checksum are good; send it over to layer5
                message = Msg(packet.payload)
                to_layer5(self, message)
            
            # send ACK
            ack = Pkt(seqnum = packet.seqnum, acknum = packet.seqnum, checksum = 0, payload = packet.payload)
            ack.checksum = calc_checksum(ack)
            
            # update last_acked and expected seqnum
            self.last_acked = packet.seqnum
            self.seqnum = (self.last_acked + 1) % self.seqnum_limit
            # print("RECEIVER: Sending ACK " + str(packet.payload) + " " + str(ack.acknum))
            to_layer3(self, ack)
        
        else:
            #send NACK, which will have an empty payload;
            # I tried to use acknum to indicate NACK, but acknum is forced to be between 0, seqnum_limit-1 so just use payload
            nack = Pkt(seqnum = self.seqnum, acknum = packet.seqnum, checksum = 0, payload = b'                    ')
            nack.checksum = calc_checksum(nack)

            # if not expected:
            #     print("RECEIVER: Sending NACK (Unexpected) for seqnum " + str(nack.acknum))
            # elif not correct_checksum:
            #     print("RECEIVER: Sending NACK (Corrupted) for seqnum " + str(nack.acknum))
            
            to_layer3(self, nack)


    # Ignore this method!
    def timer_interrupt(self):
        pass

###############################################################################

## ********************** STUDENT-CALLABLE FUNCTIONS **************************
##
## NOTICE: These are functions that should be called from your SndTransport and
## RcvTransport methods.
##
## The first argument to each of these student-callable functions is the object
## that is invoking the function.  Within an SndTransport or RcvTransport method, that
## object is available as `self`.  For example, to start a timer in one of your
## entity methods, you would do something like:
##
##   start_timer(self, 10.0) # Start a timer that will go off in 10 time units.
##
## Or to send a packet to layer3, you would do something like:
##
##   to_layer3(self, Pkt(...)) # Construct a Pkt and send it to layer3.
##
## ****************************************************************************

def start_timer(calling_entity, increment):
    sim.the_sim.start_timer(calling_entity, increment)

def stop_timer(calling_entity):
    sim.the_sim.stop_timer(calling_entity)

def to_layer3(calling_entity, packet):
    sim.the_sim.to_layer3(calling_entity, packet)

def to_layer5(calling_entity, message):
    sim.the_sim.to_layer5(calling_entity, message)

def get_time(calling_entity):
    return sim.the_sim.get_time(calling_entity)
