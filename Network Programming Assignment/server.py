#Sam Brandt
#Professor Zieglar
#CMSC 481
#December 9, 2021

#A server program that implements the bulletin board protocol described in my RFC.

from socket import *
import threading

hostName = '127.0.0.1' 

#Two functions for getting around bugs caused by "Nagle's algorithm" being default in TCP, 
#which causes multiple peices of data sent close enough together to be sent in one packet.
def bufferedSend(soc, content):
    #Send the string along with its length placed at the beginning so it can later be
    #extracted from a larger string that might be created by multiple calls to send().
    soc.send((chr(len(content)) + content).encode())
    
#Global dictionary used to store a queue of previously received strings for each thread.
previouslyRecievedContent = {}
def bufferedRecieve(soc):
    #Get list associated with the current thread.
    threadIndex = threading.get_ident()
    if not threadIndex in previouslyRecievedContent.keys():
        previouslyRecievedContent[threadIndex] = []
    threadPrc = previouslyRecievedContent[threadIndex]
    
    #If there's nothing in the queue, start receiving from the socket, otherwise return
    #the oldest thing that was previously recieved. This will synchronize the calls to
    #recieve() with the calls to send() on the other host.
    if len(threadPrc) == 0:
        #Receive what could be congealed together data from multiple send() calls from the
        #other host
        uglyPacketGoo = soc.recv(1024).decode()
        #Stores the index of the length of the substring currently being extracted
        lengthInfoIndex = 0
        #Stores the index of the length of the next substring to be extracted
        nextIndex = 0
        #Extract all substrings.
        endOfBuffer = False
        while not endOfBuffer:
            if nextIndex > 0:
                #Extract current substring of focus and add it to the end of the queue.
                extractedContent = uglyPacketGoo[lengthInfoIndex + 1:nextIndex]
                threadPrc.append(extractedContent)
                #Update the length index
                lengthInfoIndex = nextIndex
                endOfBuffer = nextIndex >= len(uglyPacketGoo)
            if nextIndex < len(uglyPacketGoo):
                #Get the next length index by using information about the current length.
                nextIndex = lengthInfoIndex + ord(uglyPacketGoo[nextIndex]) + 1
    #Return the oldest thing that was recieved.
    return threadPrc.pop(0)

#Two functions for sending and recieving data of arbitrary length. Splits the string into
#128 character chunks (to account for the possibility of more-than-one-byte unicode
#characters) and sends and recieves them one at a time.
def sendData(soc, data):
    #Inform the other host of the length of the data it will be recieving.
    bufferedSend(soc, str(len(data)))
    #Send a chunk and updates the chunk index until the whole string is sent.
    chunkStart = 0
    while (chunkStart < len(data)):
        bufferedSend(soc, data[chunkStart:min(chunkStart+128,len(data))])
        chunkStart += 128
    
def recieveData(soc):
    #The length of the data that will be recieved.
    dataLength = int(bufferedRecieve(soc))
    
    #Recieves the chunks of data one at a time and reconcatenates them into the original
    #string.
    data = ''
    charsRecieved = 0
    finished = False
    while (charsRecieved  < dataLength):
        recieved = bufferedRecieve(soc)
        data += recieved
        charsRecieved += len(recieved)
    return data

#Class for representing a single message, includes information about which users have read
#the message.
class Msg:
    def __init__(self, subject, body, sender):
        self.subject = subject
        self.body = body
        self.sender = sender
        #Counts the user that sent the message as having already read it.
        self.readers = [sender]
        
    def getSubject(self):
        return self.subject
    
    def getBody(self):
        return self.body
    
    def getSender(self):
        return self.sender
    
    def markAsRead(self, reader):
        self.readers.append(reader)
    
    def readBy(self, reader):
        return reader in self.readers
    
#Class for representing a group
class Group:
    def __init__(self, creator):
        self.creator = creator
        self.msgs = []
        
    def addMsg(self, msg):
        self.msgs.append(msg)
    
    def deleteMsg(self, msgNumber):
        del self.msgs[msgNumber]
        
    def getCreator(self):
        return self.creator
    
    def getMsgSender(self, msgNumber):
        return self.msgs[msgNumber].getSender()
        
    #Formats all of the messages indecated by the given indexes into one string.
    def __toStrEveryMsgAtIndexes(self, reader, indexes, subjectMode=False):
        string = '----------------\n'
        for i in indexes:
            string += 'Message #' + str(i + 1) + '\n'
            string += 'Sender: ' + self.msgs[i].getSender() + '\n'
            string += 'Subject: ' + self.msgs[i].getSubject() + '\n'
            #Only includes the body if 'subjectMode' is set to False.
            if not subjectMode:
                string += 'Body: ' + self.msgs[i].getBody() + '\n'
            string += '\n'
            #Any message indexed by this loop will marked as read by the reader.
            self.msgs[i].markAsRead(reader)
        #Removes the new line at the very end to make the presentation look nicer.
        if (len(indexes)):
            string = string[0:len(string) - 1]
        string += '----------------'
        return string
        
    def toStrAllMsgs(self, reader):
        string = self.__toStrEveryMsgAtIndexes(reader, range(0, len(self.msgs)))
        return string
    
    def toStrUnreadMsgs(self, reader):
        #Finds the indexes of all messages not read by the reader.
        indexes = []
        for i in range(0, len(self.msgs)):
            if not self.msgs[i].readBy(reader):
                indexes.append(i)
        
        string = self.__toStrEveryMsgAtIndexes(reader, indexes)
        return string
    
    def toStrMsg(self, reader, msgNumber):
        string = self.__toStrEveryMsgAtIndexes(reader, range(msgNumber, msgNumber + 1))
        return string
    
    def toStrAllSubjects(self, reader):
        string = self.__toStrEveryMsgAtIndexes(reader, range(0, len(self.msgs)), True)
        return string
                                               
    def getTotalMsgs(self):
        return len(self.msgs)
    
    def getUnreadMsgs(self, reader):
        #Loop to count the number of messages not read by the reader.
        numMsgsNotRead = 0
        for i in range(0, len(self.msgs)):
            if not self.msgs[i].readBy(reader):
                numMsgsNotRead += 1
        return numMsgsNotRead
        
    
#Global dictionary for storing private groups and associating them with IDs.
groups = {}
#A single group object with no creator to represent the public group.
publicGroup = Group(None)

#Name is mostly self explanatory, also handles informing the client about the ID's
#existential status.
def getIDandCheckIfItExists(connectionSocket):
    ID = recieveData(connectionSocket)
    exists = False
    if not ID in groups.keys():
        bufferedSend(connectionSocket, 'Does not exist.')
    else:
        bufferedSend(connectionSocket, 'Already exists.')
        exists = True
    return ID, exists

#Global dictionary that maps threads to booleans that allows any scope the power to force 
#the thread out of interacting with a single group.
chatModeEnded = {}

#Checks if a group still exists and forces the client thread out of chatting with said 
#group if it doesn't. This can occur when a different client deletes the group that the 
#one calling this function is interacting with.
def stillExists(connectionSocket, group):
    #Waits until the client counterpart of this function indicates it was called before
    #sending so that it sends the most up-to-date information.
    bufferedRecieve(connectionSocket)
    stillExists = False
    if group == publicGroup or group in groups.values():
        bufferedSend(connectionSocket, "Still exists.")
        stillExists = True
    else:
        bufferedSend(connectionSocket, "No longer exists.")
        chatModeEnded[threading.get_ident()] = True
        stillExists = False
    return stillExists

#Handles the server side of a user interacting with a specific group.
def chatMode(connectionSocket, currentGroup, username):
    tid = threading.get_ident()
    chatModeEnded[tid] = False
    #Repeatedly gets a choice indicator from the client and preforms the associated action.
    while not chatModeEnded[tid]:
        #Checks if the group still exists before performing any actions.
        if stillExists(connectionSocket, currentGroup):
            choice = bufferedRecieve(connectionSocket)
            #Choices 1-6 result in the server sending the client the information it
            #requested.
            if choice == '1':
                bufferedSend(connectionSocket, str(currentGroup.getTotalMsgs()))
            elif choice == '2':
                sendData(connectionSocket, currentGroup.toStrAllMsgs(username))
            elif choice == '3':
                bufferedSend(connectionSocket, str(currentGroup.getUnreadMsgs(username)))
            elif choice == '4':
                sendData(connectionSocket, currentGroup.toStrUnreadMsgs(username))
            elif choice == '5':
                if stillExists(connectionSocket, currentGroup):
                    #Get's the number of the client's requested message.
                    msgNumber = bufferedRecieve(connectionSocket)
                    #Disregard the choice to send a specific message if there was an error
                    #in the user's input detected by the client.
                    if msgNumber != "Disregard choice.":
                        #Convert into list index format.
                        msgNumber = int(msgNumber) - 1
                        #Indicates to the client whether a message with that number exists
                        #before sending the message.
                        if msgNumber >= currentGroup.getTotalMsgs():
                            bufferedSend(connectionSocket, 'Out of range.')
                        else:
                            bufferedSend(connectionSocket, 'In range.')
                            sendData(connectionSocket, currentGroup.toStrMsg(username, msgNumber))
            elif choice == '6':
                sendData(connectionSocket, currentGroup.toStrAllSubjects(username))
            elif choice == '7':
                #Get subject and message information from the user, creates a new Msg
                #object, and adds it to the group.
                if stillExists(connectionSocket, currentGroup):
                    subject = recieveData(connectionSocket)
                    if stillExists(connectionSocket, currentGroup):
                        body = recieveData(connectionSocket)
                        currentGroup.addMsg(Msg(subject, body, username))
            elif choice == '8':
                if stillExists(connectionSocket, currentGroup):
                    #See the comments in the scope below 'elif choice == 5:' to understand
                    #the checks for msgNumber.
                    msgNumber = bufferedRecieve(connectionSocket)
                    if msgNumber != "Disregard choice.":
                        msgNumber = int(msgNumber) - 1
                        if msgNumber >= currentGroup.getTotalMsgs():
                            bufferedSend(connectionSocket, 'Out of range.')
                        else:
                            bufferedSend(connectionSocket, 'In range.')
                            #Checks if the message was sent by the same user trying to
                            #delete it and inform's the client of the result of this check
                            #before deleting the message.
                            if username == currentGroup.getMsgSender(msgNumber):
                                bufferedSend(connectionSocket, "Success.")
                                currentGroup.deleteMsg(msgNumber)
                            else:
                                bufferedSend(connectionSocket, "Not the sender.")
            elif choice == '9':
                #End's the interaction with this chat in accordance to the client's wishes.
                chatModeEnded[tid] = True
                

def manageConnection(connectionSocket):
    #Recieves the username associated with this client.
    username = recieveData(connectionSocket)
    print(username + " has connected.")
    
    #Repeatedly gets a choice indicator from the client and preforms the associated action.
    sessionClosed = False
    while not sessionClosed:
        choice = bufferedRecieve(connectionSocket)
        if choice == '1':
            #Begins an interaction with the public group.
            chatMode(connectionSocket, publicGroup, username)
        elif choice == '2':
            #Begins an interaction with the requested private group if it exists.
            ID, exists = getIDandCheckIfItExists(connectionSocket)
            if exists:
                chatMode(connectionSocket, groups[ID], username)
        elif choice == '3':
            #Create a group with the requested ID if it doesn't already exist.
            ID, exists = getIDandCheckIfItExists(connectionSocket)
            if not exists:
                groups[ID] = Group(username)
        elif choice == '4':
            #Delete the group with the requested ID if it exists and was created by the 
            #user requesting for it to be deleted.
            ID, exists = getIDandCheckIfItExists(connectionSocket)
            if exists:
                if (username == groups[ID].getCreator()):
                    bufferedSend(connectionSocket, "Success.")
                    del groups[ID]
                else:
                    bufferedSend(connectionSocket, "Not the creator.")
        elif choice == '5':
            #Exists the loop, closes the connection, and ends the thread.
            sessionClosed = True
            
    print(username + " has disconnected.")
    connectionSocket.close()
    tid = threading.get_ident()
    if tid in previouslyRecievedContent.keys():
        del previouslyRecievedContent[tid]
    if tid in chatModeEnded.keys():
        del chatModeEnded[tid]

#Global socket variable for the server.
serverSocket = socket(AF_INET, SOCK_STREAM)
serverSocket.bind((hostName, 13037))
serverSocket.listen(1)
print('On.')
while True:
    #Gets the connection specific socket if a client starts a connection and passes it to
    #a new thread to manage it concurrently with the other connections.
    connectionSocket, addr = serverSocket.accept()
    connectionThread = threading.Thread(target=manageConnection, args=(connectionSocket,))
    connectionThread.start()