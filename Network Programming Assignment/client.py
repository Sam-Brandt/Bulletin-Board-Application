#Sam Brandt
#Professor Zieglar
#CMSC 481
#December 9, 2021

#A client program that implements the bulletin board protocol described in my RFC.

from socket import *

serverName = '127.0.0.1'
 
#Two functions for getting around bugs caused by "Nagle's algorithm" being default in TCP, 
#which causes multiple peices of data sent close enough together to be sent in one packet.
def bufferedSend(soc, content):
    #Send the string along with its length placed at the beginning so it can later be
    #extracted from a larger string that might be created by multiple calls to send().
    soc.send((chr(len(content)) + content).encode())
    
#Global queue of previously received strings.
previouslyRecievedContent = []
def bufferedRecieve(soc):
    #If there's nothing in the queue, start receiving from the socket, otherwise return
    #the oldest thing that was previously recieved. This will synchronize the calls to
    #recieve() with the calls to send() on the other host.
    if len(previouslyRecievedContent) == 0:
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
                previouslyRecievedContent.append(extractedContent)
                #Update the length index
                lengthInfoIndex = nextIndex
                endOfBuffer = nextIndex >= len(uglyPacketGoo)
            if nextIndex < len(uglyPacketGoo):
                #Get the next length index by using information about the current length.
                nextIndex = lengthInfoIndex + ord(uglyPacketGoo[nextIndex]) + 1
    #Return the oldest thing that was recieved.
    return previouslyRecievedContent.pop(0)

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

#Global socket varialble for the client.
clientSocket = socket(AF_INET, SOCK_STREAM)

#Global boolean variable that gives any scope the power to force the program out of 
#interacting with a single group. Wrapped by a list to get around python's weird rule that 
#makes only reference types straightforward global variables.
chatEnded = [False]

#Gets information from the server about whether the group the client is interacting with 
#still exists and forces the program out of chatting with said group if it doesn't.
def groupStillExists():
    #Indicates to the server that this function was called.
    bufferedSend(clientSocket, "Ready for info.")
    serverInfo = bufferedRecieve(clientSocket)
    if serverInfo == "No longer exists.":
        print("\nThe group you were interacting with was deleted.")
        chatEnded[0] = True
        return False
    elif serverInfo == "Still exists.":
        return True

#Handles the recurring need in other parts of the program for the user to input a number that corresponds to as message, preform various checks that involve both the client
#and the server, and inform the user if any of the checks failed.
def getMsgNumberAndSendToServer():
    msgNumber = input('> ')
    if groupStillExists():
        #Checks if the input is in the format of a positive integer and tells the server
        #disregard the user's previously sent chat mode choice if it isn't.
        if not msgNumber.isnumeric() or msgNumber == '0':
            print('\nYour input must be a positive integer.')
            bufferedSend(clientSocket, "Disregard choice.")
        else:
            bufferedSend(clientSocket, msgNumber)
            #Return's true or false based on the server's indication of if a message
            #with that number.
            serverResponse = bufferedRecieve(clientSocket)
            if serverResponse == "Out of range.":
                print('\nThe number you entered is greater than the number of messages in this group.')
                return False
            elif serverResponse == "In range.":
                return True

def chatState():
    #Repeatedly asks the user for a choice, sends the choice to the server, and handle's 
    #the client part of the corresponding action.
    chatEnded[0] = False
    while not chatEnded[0]:
        print('What would you like to do?')
        print('1 - Get total number of messages.')
        print('2 - Read all messages.')
        print('3 - Get number of new messages.')
        print('4 - Read new messages.')
        print('5 - Read specific message.')
        print('6 - Just read message subjects.')
        print('7 - Send message.')
        print('8 - Delete message.')
        print('9 - Stop interacting with this group.')
        choice = input('> ')
        #Checks if the group still exists after every input from the user.
        if groupStillExists():
            if len(choice) > 1:
                bufferedSend(clientSocket, '0')
            else:
                bufferedSend(clientSocket, choice)
            #Recieves the requested data from the server and prints it for choices 1-6.
            if choice == '1':
                serverResponse = bufferedRecieve(clientSocket)
                print('\n' + serverResponse + ' messages sent to this group total.')
            elif choice == '2':
                serverResponse = recieveData(clientSocket)
                print('\n' + serverResponse)
            elif choice == '3':
                serverResponse = bufferedRecieve(clientSocket)
                print('\n' + serverResponse + ' new messages.')
            elif choice == '4':
                serverResponse = recieveData(clientSocket)
                print('\n' + serverResponse)
            elif choice == '5':
                #Gets a message number from the user and sends it to the server first.
                print('\nEnter the number of the message you want to read.')
                if getMsgNumberAndSendToServer():
                    serverResponse = recieveData(clientSocket)
                    print('\n' + serverResponse)
            elif choice == '6':
                serverResponse = recieveData(clientSocket)
                print('\n' + serverResponse)
            elif choice == '7':
                #Asks the user to provide a subject and a body for their message and sends
                #them to the server.
                print()
                subject = input("Subject: ")
                if groupStillExists():
                    sendData(clientSocket, subject)
                    body = input("Body: ")
                    if groupStillExists():
                        sendData(clientSocket, body)
            elif choice == '8':
                #Gets a message number from the user and sends it to the server first.
                print('\nEnter the number of the message you want to delete.')
                if getMsgNumberAndSendToServer():
                    serverResponse = bufferedRecieve(clientSocket)
                    #Informs the user if the server indicates that they are not the creator.
                    if serverResponse == "Not the sender.":
                        print('\nYou must be the sender of the message that you are deleting.')
                    elif serverResponse == "Success.":
                        print('\nYour requested message was deleted successfully.')
            elif choice == '9':
                #End's the interaction with this chat in accordance to the user's wishes.
                chatEnded[0] = True
            else:
                print('\nNot a valid input.')

        print()
        

#Asks the user to provide their username.
print('Welcome to Bulletin Net v0.314159!\n')
print('Enter your username: ')
username = input('> ')
print()

#Connects to the server and sends it the username.
clientSocket.connect((serverName, 13037))
sendData(clientSocket, username)

#Repeatedly asks the user for a choice, sends the choice to the server, and handle's the 
#client part of the corresponding action.
sessionEnded = False
while not sessionEnded:
    print('What would you like to do?')
    print('1 - Interact with the public group.')
    print('2 - Interact with a private group.')
    print('3 - Create a new group.')
    print('4 - Delete an existing group.')
    print('5 - Exit.')
    choice = input('> ')
    if len(choice) > 1:
        bufferedSend(clientSocket, '0')
    else:
        bufferedSend(clientSocket, choice)
    if choice == '1':
        #Begins the chat state.
        print('\n\nYou are now interacting with the public group!\n')
        chatState()
    elif choice == '2':
        #Gets an ID from the user, tells the server to check if it exists, and if
        #it does, begins the chat state.
        print('\nInput the ID of the group you wish to interact with.')
        ID = input('> ')
        sendData(clientSocket, ID)
        serverResponse = bufferedRecieve(clientSocket)
        if serverResponse == 'Does not exist.':
            print('\nNo group exists with the ID: ' + ID)
        elif serverResponse == "Already exists.":
            print('\n\nYou are now interacting with your requested group!\n')
            chatState()
    elif choice == '3':
        #Gets an ID from the user, tells the server to check if it already exists, and if
        #it doesn't, the client indicates to the user that a new group was created.
        print('\nGive your group an ID.')
        ID = input('> ')
        sendData(clientSocket, ID)
        serverResponse = bufferedRecieve(clientSocket)
        if serverResponse == 'Already exists.':
            print('\nAnother group exists with that ID, try another one.')
        elif serverResponse == "Does not exist.":
            print('\nYour group was created successfully.')
    elif choice == '4':
        #Gets an ID from the user, tells the server to check if it exists, and if
        #it does, the client indicates to the user that a new group was created and was
        #created by this user, and if it does and was, the client indicates to the user
        #that the group was deleted.
        print('\nInput the ID of the group you wish to delete')
        ID = input('> ')
        sendData(clientSocket, ID)
        serverResponse = bufferedRecieve(clientSocket)
        if serverResponse == 'Does not exist.':
            print('\nNo group exists with the ID: ' + ID)
        elif serverResponse == "Already exists.":
            secondServerResponse = bufferedRecieve(clientSocket)
            if secondServerResponse == "Not the creator.":
                print('\nYou must be the creator of the group that you are deleting.')
            elif secondServerResponse == "Success.":
                print('\nYour requested group was deleted successfully.')
    elif choice == '5':
        #Exits the loop and closes the connection.
        sessionEnded = True
    else:
        print('\nNot a valid input.')
        
    print()

clientSocket.close()

print("Goodbye!")