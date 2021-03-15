# Author: George Kochera
# Date: 3/12/2021
# Name: server.py
# Description: Used to spin up the server process and when run as script, will
# also start a client on the server machine
# Sources: See README.md

import socket, select, time, sys
from threading import *
from multiprocessing import *
from client import client

# PORT NUMBER TO USE
PORT = 38742

# MAXIMUM CONNECTIONS TO ACCEPT AT ONE TIME
MAX_CONNECTIONS = 12

# List of sockets the server will listen to messages from
socket_list = []

# Keep the name of the server user None at first, this is populated by the 
# first connected user, and used to shut the server down in non-persistent
# mode when the server user enters \q
server_user = None


# Tells all chat members that someone has joined the chat
def joined_chat(connection_socket):
    
    global server_user

    # Get the name
    id = connection_socket.recv(120)
    id = str(id, 'utf-8')

    # If this is the first connection (should be the server user), set that
    # global variable
    if server_user is None:
        server_user = id

    # Create the join message
    message = "SERVER: {} has joined the chat!".format(id)

    # Send it to everyone!
    for element in socket_list:
        element.send(bytes(message, 'utf-8'))


# Checks to see if the user disconnected: returns false if they did not, other
# wise true
def user_did_disconnect(message: bytes):

    # Convert the message to a string
    message = str(message, 'utf-8')

    # Enclose in a try block incase the message isn't long enough
    try:

        # Grab the expected length of the enclosing disconnect characters
        prefix = message[:3]
        suffix = message[-3:]

    # Return false if the message wasn't long enough, we know the user didn't 
    # disconnect
    except:
        return False

    # Evaluate if the characters were the disconnect characters and return
    # True if they were
    else:
        if prefix == "-~~" and suffix == "~~-":
            return True
        else:
            return False


# Listens for a message on the current thread and if one comes in, it will then
# broadcast the message back to the all the clients.
def listen_for_messages(connection_socket):

    # Announce the arrival of a new member
    joined_chat(connection_socket)

    # We keep waiting for messages until we get the kill string
    active = True
    while active:

        # Receive a message
        message = connection_socket.recv(120)

        # If its the kill string, we set this thread to inactive, remove the
        # socket from the socket_list and close the socket on our end
        if user_did_disconnect(message):
            active = False
            socket_list.remove(connection_socket)
            connection_socket.close()
            name = str(message, 'utf-8')[3:-3]
            str_message = "SERVER: {} has left the chat...".format(name)
            for element in socket_list:
                element.send(bytes(str_message, 'utf-8'))

        # Otherwise we broadcast the message to all clients
        else:
            for element in socket_list:
                element.send(message)


# Main server funtction, starts up a listener socket then continuously
# waits for new clients spinning them off into new threads for further servicing
def server(persistent=False):

    # Create the socket
    listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Listen for inbound connections on the local host
    listener_socket.bind((socket.gethostname(), PORT))
    listener_socket.listen(MAX_CONNECTIONS)
    listener_socket.setblocking(False)

    # Keep track of the first connection which should be the server user, it
    # starts as none, and then becomes the thread when that user connects, we
    # evaluate it to see if it ended, to shut down the server in non-persistent
    # mode
    server_user_thread = None

    # Keep this true for start up, we use this as a latch for the number of
    # sockets in our socket_list, once at least one connection is made, this goes
    # to false
    running = True
    clients_connected = False

    # Wait for an incoming connection
    while running:

        # Use select to scan the listener socket for readable events
        (readable, writable, error) = select.select([listener_socket],[],[], 0.25)
        if readable:
            (connection_socket, address) = listener_socket.accept()

            # Add it to the list of sockets
            socket_list.append(connection_socket)
            clients_connected = True


            # Then send the newly created socket to a new thread to be continuously 
            # monitored, start it
            client_thread = Thread(target=listen_for_messages, args=(connection_socket,))
            client_thread.start()

            # Save the client thread if its the first one (will be the server
            # user)
            if server_user_thread is None:
                server_user_thread = client_thread
        
        # Check the status of the server user, if they disconnected we shut down
        # for non-persistent mode
        if not persistent and server_user_thread is not None:
            if not server_user_thread.is_alive():

                # When shutting down, we close each socket connected to us
                for element in socket_list:
                    element.send(bytes("SERVER: Disconnected... Good-bye!", 'utf-8'))
                    element.close()
                running = False

    
        # Once all the clients have disconnected, the server shuts down
        elif len(socket_list) == 0 and clients_connected:
            running = False
    
    # Clean up and close the listener socket
    listener_socket.close()
    return None


# When run as a script do...
if __name__ == "__main__":
    
    try:
        if sys.argv[1] == '-p':
            print("Running server in persistent mode...")
            # Start the server as a new process
            server_process = Process(target=server,kwargs={'persistent': True})
            server_process.start()

            # Show the client GUI
            client()

            # Wait for clients to close so server.py can terminate
            print("Waiting for remaining clients to leave the chat (CTRL + C to force shutdown!)")
    
    except IndexError:
        # Start the server as a new process
        server_process = Process(target=server)
        server_process.start()

        # Show the client GUI
        client()

        # Wait for the server to finish running
        server_process.terminate()
        server_process.join()